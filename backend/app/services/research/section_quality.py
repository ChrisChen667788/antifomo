from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
import re

from app.schemas.research import ResearchEntityEvidenceOut
from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class SectionQualityDependencies:
    source_text: Callable[[SourceDocument], str]
    tokenize_for_match: Callable[..., list[str]]
    concrete_rows: Callable[[Iterable[str]], list[str]]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    generic_focus_tokens: Collection[str]


CONFLICT_POSITIVE_TOKENS = (
    "已发布",
    "已启动",
    "已上线",
    "已签约",
    "已合作",
    "落地",
    "上线",
    "签约",
    "合作",
    "中标",
    "确认",
    "明确",
    "获批",
    "推进",
)
CONFLICT_NEGATIVE_TOKENS = (
    "尚未",
    "暂无",
    "未披露",
    "未启动",
    "未合作",
    "否认",
    "辟谣",
    "传闻",
    "未经证实",
    "推迟",
    "延后",
    "取消",
    "不涉及",
    "未见",
)


def excerpt_for_evidence(
    source: SourceDocument,
    *,
    matched_terms: list[str] | None = None,
    deps: SectionQualityDependencies,
) -> str:
    terms = [term for term in (matched_terms or []) if normalize_text(term)]
    candidates = re.split(r"[。！？!?；;\n]", deps.source_text(source))
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if not normalized:
            continue
        if terms and any(term.lower() in normalized.lower() for term in terms):
            return normalized[:140]
    fallback = normalize_text(source.excerpt or source.snippet or source.title)
    return fallback[:140]


def section_confidence_profile(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    meets_evidence_quota: bool,
    evidence_links: list[ResearchEntityEvidenceOut],
    deps: SectionQualityDependencies,
) -> tuple[str, str, str, bool, str]:
    anchor_terms = [
        token
        for token in deps.tokenize_for_match(section_title, *items[:3])
        if len(token) >= 2 and token not in deps.generic_focus_tokens
    ][:8]
    matched_texts: list[str] = []
    matched_urls = {normalize_text(link.url) for link in evidence_links if normalize_text(link.url)}
    for source in sources:
        source_text = deps.source_text(source)
        if normalize_text(source.url) in matched_urls:
            matched_texts.append(source_text)
            continue
        if anchor_terms and any(term.lower() in source_text.lower() for term in anchor_terms):
            matched_texts.append(source_text)
    positive_hits = sum(1 for text in matched_texts if any(token in text for token in CONFLICT_POSITIVE_TOKENS))
    negative_hits = sum(1 for text in matched_texts if any(token in text for token in CONFLICT_NEGATIVE_TOKENS))
    contradiction_detected = positive_hits > 0 and negative_hits > 0
    contradiction_note = (
        f"{section_title} 的相关来源里同时出现了确认性和否定/未证实表述，当前应按冲突信息处理。"
        if contradiction_detected
        else ""
    )
    if contradiction_detected:
        return "conflict", "交叉验证冲突", contradiction_note, True, contradiction_note
    if meets_evidence_quota and official_source_ratio >= 0.35 and evidence_density == "high" and source_quality != "low":
        return "high", "高置信结论", f"{section_title} 已满足证据配额，且有较高官方源占比与多源支撑。", False, ""
    return "low", "待补证结论", f"{section_title} 当前仍需继续补官方源、交叉验证或增加直接证据。", False, ""


def extract_section_anchor_terms(section_title: str, items: list[str]) -> list[str]:
    seeds = [normalize_text(section_title)] + [normalize_text(item) for item in items[:4]]
    phrases: list[str] = []
    split_markers = ("正在", "围绕", "通過", "通过", "面向", "提供", "推进", "布局", "联合", "依托", "适合", "加速")
    for seed in seeds:
        if not seed:
            continue
        primary = re.split(r"[：:；;。.!?\n]", seed, maxsplit=1)[0].strip()
        if len(primary) >= 4 and primary not in phrases:
            phrases.append(primary)
        for marker in split_markers:
            if marker not in primary:
                continue
            head = primary.split(marker, 1)[0].strip(" ，,、；;:：")
            if 2 <= len(head) <= 24 and head not in phrases:
                phrases.append(head)
        for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", seed):
            lowered = token.lower()
            if len(lowered) >= 2 and lowered not in phrases:
                phrases.append(lowered)
    return phrases[:16]


def build_section_evidence_links(
    *,
    section_title: str,
    items: list[str],
    sources: list[SourceDocument],
    limit: int = 3,
    deps: SectionQualityDependencies,
) -> tuple[list[ResearchEntityEvidenceOut], dict[str, int], float]:
    anchor_terms = extract_section_anchor_terms(section_title, items)
    if not anchor_terms or not sources:
        return [], {}, 0.0
    scored: list[tuple[int, SourceDocument, list[str]]] = []
    for source in sources:
        haystack = normalize_text(
            " ".join(
                part
                for part in [
                    source.title,
                    source.snippet,
                    source.excerpt,
                    source.search_query,
                    source.source_label or "",
                ]
                if normalize_text(part)
            )
        ).lower()
        if not haystack:
            continue
        matched_terms = [term for term in anchor_terms if term and term.lower() in haystack]
        if not matched_terms:
            continue
        score = len(matched_terms) * 5
        if source.source_tier == "official":
            score += 8
        elif source.source_tier == "aggregate":
            score += 3
        if normalize_text(section_title).lower() and normalize_text(section_title).lower() in haystack:
            score += 4
        scored.append((score, source, matched_terms[:3]))
    if not scored:
        return [], {}, 0.0
    scored.sort(
        key=lambda item: (
            item[0],
            1 if item[1].source_tier == "official" else 0,
            len(item[2]),
        ),
        reverse=True,
    )
    support_rows = scored[: max(limit + 2, 4)]
    tier_counts: Counter[str] = Counter()
    for _, source, _ in support_rows:
        tier_counts[source.source_tier or "media"] += 1
    official_ratio = (
        float(tier_counts.get("official", 0)) / max(sum(tier_counts.values()), 1)
        if tier_counts
        else 0.0
    )
    links: list[ResearchEntityEvidenceOut] = []
    seen_urls: set[str] = set()
    for _, source, matched_terms in scored:
        if source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        links.append(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=source.url,
                source_label=source.source_label,
                source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
                anchor_text=" / ".join(matched_terms[:2]),
                excerpt=excerpt_for_evidence(source, matched_terms=matched_terms[:2], deps=deps),
            )
        )
        if len(links) >= max(1, limit):
            break
    return links, dict(tier_counts), round(official_ratio, 3)


def section_signal_quality(
    items: list[str],
    sources: list[SourceDocument],
    *,
    evidence_links: list[ResearchEntityEvidenceOut] | None = None,
    source_tier_counts: dict[str, int] | None = None,
    official_source_ratio: float = 0.0,
    deps: SectionQualityDependencies,
) -> tuple[str, str, str]:
    concrete_count = len(deps.concrete_rows(items))
    tier_counts = Counter(source_tier_counts or {})
    support_count = sum(tier_counts.values()) if tier_counts else len(evidence_links or [])
    official_count = int(tier_counts.get("official", 0))
    anchor_count = len(evidence_links or [])
    if concrete_count >= 3 and support_count >= 3 and official_count >= 1:
        return "high", "high", f"已锚定 {anchor_count or support_count} 条来源，其中官方源占比较高。"
    if concrete_count >= 2 and support_count >= 2:
        return (
            "medium",
            "medium" if official_count >= 1 or official_source_ratio >= 0.3 else "low",
            f"已锚定 {anchor_count or support_count} 条来源，建议继续补官方源与专项交叉验证。",
        )
    if concrete_count >= 2 and sources:
        return "medium", "medium" if official_count >= 1 else "low", "已有可用线索，建议继续补更多定向证据。"
    return "low", "low" if official_count == 0 else "medium", "当前证据较弱，更多结论应视为待验证线索。"


def section_evidence_quota(section_key: str, items: list[str]) -> int:
    critical_sections = {
        "commercial_opportunities",
        "sales_strategy",
        "bidding_strategy",
        "outreach_strategy",
        "target_accounts",
        "target_departments",
        "public_contact_channels",
        "budget_signals",
        "tender_timeline",
        "ecosystem_partners",
        "competitor_profiles",
        "benchmark_cases",
    }
    if section_key in critical_sections:
        return 2 if len(items) >= 2 else 1
    if len(items) >= 4:
        return 2
    return 1 if items else 0


def section_quota_note(
    *,
    section_title: str,
    evidence_count: int,
    evidence_quota: int,
    official_source_ratio: float,
) -> tuple[bool, int, str]:
    if evidence_quota <= 0:
        return True, 0, ""
    quota_gap = max(evidence_quota - evidence_count, 0)
    if quota_gap <= 0:
        if official_source_ratio >= 0.3:
            return True, 0, f"{section_title} 已满足证据配额，且已有官方源支撑。"
        return True, 0, f"{section_title} 已满足证据配额。"
    if evidence_count >= 1 and official_source_ratio >= 0.35:
        return True, 0, f"{section_title} 当前证据条数未满配额，但已有官方源可作为首轮判断支撑。"
    return False, quota_gap, f"{section_title} 还缺 {quota_gap} 条高相关证据，建议继续补官方源或专项交叉验证。"


def section_next_verification_steps(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    evidence_count: int,
    evidence_quota: int,
    contradiction_detected: bool,
    deps: SectionQualityDependencies,
) -> list[str]:
    normalized_title = normalize_text(section_title).lower()
    quota_gap = max(int(evidence_quota or 0) - int(evidence_count or 0), 0)
    steps: list[str] = []

    if any(token in normalized_title for token in ("联系", "contact", "部门", "department", "商务", "组织")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网联系页、采购公告联系人和公开职责说明",
                "zh-TW": "官網聯絡頁、採購公告聯絡人與公開職責說明",
                "en": "official contact pages, procurement contacts, and public org-role pages",
            },
            "官网联系页、采购公告联系人和公开职责说明",
        )
    elif any(token in normalized_title for token in ("预算", "招标", "投标", "采购", "项目", "tender", "budget", "project")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "采购公告、招标文件、预算批复和项目立项/中标公告",
                "zh-TW": "採購公告、招標文件、預算批覆與專案立項/中標公告",
                "en": "procurement notices, tender files, budget approvals, and project / award notices",
            },
            "采购公告、招标文件、预算批复和项目立项/中标公告",
        )
    elif any(token in normalized_title for token in ("竞品", "伙伴", "生态", "案例", "benchmark", "partner", "competitor")):
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网案例页、合作发布和中标/落地公告",
                "zh-TW": "官網案例頁、合作發布與中標/落地公告",
                "en": "official case pages, partnership releases, and award / deployment announcements",
            },
            "官网案例页、合作发布和中标/落地公告",
        )
    else:
        source_hint = localized_text(
            output_language,
            {
                "zh-CN": "官网、政策/采购公告和公开披露页",
                "zh-TW": "官網、政策/採購公告與公開披露頁",
                "en": "official sites, policy / procurement notices, and public disclosure pages",
            },
            "官网、政策/采购公告和公开披露页",
        )

    if contradiction_detected:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"优先回到 {source_hint} 核对冲突口径，并把“已确认 / 待确认”线索分开记录。",
                    "zh-TW": f"優先回到 {source_hint} 核對衝突口徑，並把「已確認 / 待確認」線索分開記錄。",
                    "en": f"Recheck conflicting claims against {source_hint}, and separate confirmed vs. pending signals.",
                },
                f"优先回到 {source_hint} 核对冲突口径，并把“已确认 / 待确认”线索分开记录。",
            )
        )
    if quota_gap > 0:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"至少再补 {quota_gap} 条高相关公开证据，优先从 {source_hint} 里补齐。",
                    "zh-TW": f"至少再補 {quota_gap} 條高相關公開證據，優先從 {source_hint} 補齊。",
                    "en": f"Add at least {quota_gap} more high-relevance public evidence items, prioritizing {source_hint}.",
                },
                f"至少再补 {quota_gap} 条高相关公开证据，优先从 {source_hint} 里补齐。",
            )
        )
    if official_source_ratio < 0.3:
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"至少补 1 条来自 {source_hint} 的官方或准官方来源，降低媒体/聚合源偏差。",
                    "zh-TW": f"至少補 1 條來自 {source_hint} 的官方或準官方來源，降低媒體/聚合來源偏差。",
                    "en": f"Add at least one official or near-official source from {source_hint} to reduce media / aggregator bias.",
                },
                f"至少补 1 条来自 {source_hint} 的官方或准官方来源，降低媒体/聚合源偏差。",
            )
        )
    if evidence_density == "low" or source_quality == "low":
        steps.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"把 {section_title} 拆成更具体的实体、项目编号或时间窗，再做一轮定向补证。",
                    "zh-TW": f"把 {section_title} 拆成更具體的實體、專案編號或時間窗，再做一輪定向補證。",
                    "en": f"Split {section_title} into more concrete entities, project IDs, or time windows before another targeted evidence pass.",
                },
                f"把 {section_title} 拆成更具体的实体、项目编号或时间窗，再做一轮定向补证。",
            )
        )
    return deps.dedupe_strings(steps, 3)


def section_insufficiency_profile(
    *,
    section_title: str,
    output_language: str,
    evidence_density: str,
    source_quality: str,
    official_source_ratio: float,
    quota_gap: int,
    contradiction_detected: bool,
    deps: SectionQualityDependencies,
) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    if contradiction_detected:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "当前存在冲突表述，需先回到同一口径核对“已确认 / 待确认”信息。",
                    "zh-TW": "目前存在衝突表述，需先回到同一口徑核對「已確認 / 待確認」資訊。",
                    "en": "Conflicting claims are present. Recheck confirmed vs. pending signals against a consistent source set first.",
                },
                "当前存在冲突表述，需先回到同一口径核对“已确认 / 待确认”信息。",
            )
        )
    if quota_gap > 0:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": f"高相关证据配额仍缺 {quota_gap} 条，当前结论还不够稳。",
                    "zh-TW": f"高相關證據配額仍缺 {quota_gap} 條，目前結論仍不夠穩。",
                    "en": f"The section is still short of {quota_gap} high-relevance evidence items.",
                },
                f"高相关证据配额仍缺 {quota_gap} 条，当前结论还不够稳。",
            )
        )
    if official_source_ratio < 0.3:
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "官方或准官方来源占比偏低，媒体/聚合源偏差还没有压下来。",
                    "zh-TW": "官方或準官方來源佔比偏低，媒體/聚合來源偏差仍未壓下來。",
                    "en": "Official or near-official source coverage is still too low.",
                },
                "官方或准官方来源占比偏低，媒体/聚合源偏差还没有压下来。",
            )
        )
    if evidence_density == "low":
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "直接证据密度偏低，章节判断更多还是线索归纳，不是强验证结论。",
                    "zh-TW": "直接證據密度偏低，章節判斷仍偏線索歸納，還不是強驗證結論。",
                    "en": "Direct evidence density is low, so this section is still more indicative than verified.",
                },
                "直接证据密度偏低，章节判断更多还是线索归纳，不是强验证结论。",
            )
        )
    if source_quality == "low":
        reasons.append(
            localized_text(
                output_language,
                {
                    "zh-CN": "来源质量偏低，仍需补更多官方页、采购页或公开披露页。",
                    "zh-TW": "來源品質偏低，仍需補更多官方頁、採購頁或公開披露頁。",
                    "en": "Source quality is low; more official, procurement, or disclosure pages are needed.",
                },
                "来源质量偏低，仍需补更多官方页、采购页或公开披露页。",
            )
        )

    deduped = deps.dedupe_strings(reasons, 4)
    if contradiction_detected or quota_gap > 0 or evidence_density == "low":
        status = "needs_evidence"
    elif deduped:
        status = "degraded"
    else:
        status = "ready"
    if deduped:
        summary = localized_text(
            output_language,
            {
                "zh-CN": f"{section_title} 当前仍未达到稳定推进门槛：{'；'.join(deduped[:2])}",
                "zh-TW": f"{section_title} 目前仍未達到穩定推進門檻：{'；'.join(deduped[:2])}",
                "en": f"{section_title} is still below the execution threshold: {'; '.join(deduped[:2])}",
            },
            f"{section_title} 当前仍未达到稳定推进门槛：{'；'.join(deduped[:2])}",
        )
    else:
        summary = localized_text(
            output_language,
            {
                "zh-CN": f"{section_title} 当前章节证据结构已达到首轮推进门槛。",
                "zh-TW": f"{section_title} 目前章節證據結構已達到首輪推進門檻。",
                "en": f"{section_title} has reached the first-pass evidence threshold.",
            },
            f"{section_title} 当前章节证据结构已达到首轮推进门槛。",
        )
    return status, deduped, summary
