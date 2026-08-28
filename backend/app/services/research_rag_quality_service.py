from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Iterable, Literal

from app.services.content_extractor import normalize_text


_TERM_RE = re.compile(r"[a-z0-9][a-z0-9._/-]{1,}|[\u4e00-\u9fff]{2,}", flags=re.IGNORECASE)
_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;\n]+")

_STOPWORDS = {
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
    "the",
    "and",
    "for",
    "with",
    "what",
    "which",
    "their",
    "about",
}

_OFFICIAL_HINTS = (
    "gov.cn",
    ".gov",
    "ccgp",
    "ggzy",
    "cecbid",
    "edu.cn",
    "org.cn",
    "官网",
    "官方",
)
_PROCUREMENT_TERMS = ("招标", "中标", "采购", "采购意向", "成交", "竞争性磋商", "预算", "最高限价", "合同金额", "项目")
_SOLUTION_TERMS = ("方案", "平台", "系统", "产品", "技术参数", "接口", "部署", "试点", "扩容", "集成", "交付")
_ACTION_TERMS = ("下一步", "验证", "核验", "拜访", "标前", "投标", "客户", "部门", "伙伴", "竞品")


@dataclass(slots=True)
class CragSourceGrade:
    title: str
    url: str
    status: Literal["accepted", "ambiguous", "rejected"]
    relevance_score: int
    source_tier: str = "media"
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RetrievalCorrectionProfile:
    status: Literal["ready", "needs_filtering", "needs_expansion"]
    relevance_score: int
    accepted_source_count: int
    ambiguous_source_count: int
    rejected_source_count: int
    grades: list[CragSourceGrade] = field(default_factory=list)
    corrective_queries: list[str] = field(default_factory=list)
    compressed_context: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)

    @property
    def accepted_urls(self) -> set[str]:
        return {grade.url for grade in self.grades if grade.status == "accepted" and grade.url}

    @property
    def ambiguous_urls(self) -> set[str]:
        return {grade.url for grade in self.grades if grade.status == "ambiguous" and grade.url}

    @property
    def rejected_urls(self) -> set[str]:
        return {grade.url for grade in self.grades if grade.status == "rejected" and grade.url}

    def to_diagnostics_update(self) -> dict[str, object]:
        return {
            "retrieval_relevance_score": self.relevance_score,
            "correction_status": self.status,
            "accepted_source_count": self.accepted_source_count,
            "ambiguous_source_count": self.ambiguous_source_count,
            "rejected_source_count": self.rejected_source_count,
            "corrective_query_plan": self.corrective_queries,
            "correction_notes": self.review_notes,
        }


@dataclass(slots=True)
class GenerationGroundingReview:
    grounding_score: int
    response_quality_score: int
    supported_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)

    def to_diagnostics_update(self) -> dict[str, object]:
        return {
            "generation_grounding_score": self.grounding_score,
            "response_quality_score": self.response_quality_score,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "generation_review_notes": self.review_notes,
        }


@dataclass(slots=True)
class CrossEncoderRerankProfile:
    enabled: bool
    model_name: str
    top_k: int
    reranked_count: int = 0
    backend: str = "local-cross-encoder-style"
    notes: list[str] = field(default_factory=list)

    def to_diagnostics_update(self) -> dict[str, object]:
        return {
            "reranker_used": self.enabled and self.reranked_count > 0,
            "reranker_model": self.model_name,
            "reranker_top_k": self.top_k,
            "reranker_backend": self.backend,
            "reranker_notes": self.notes,
        }


def _dedupe_strings(values: Iterable[object], limit: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _terms(text: str, *, limit: int = 64) -> list[str]:
    normalized = normalize_text(text).lower()
    rows: list[str] = []
    for raw in _TERM_RE.findall(normalized):
        token = normalize_text(raw).lower()
        if not token or token in _STOPWORDS:
            continue
        rows.append(token)
        if _CJK_RE.match(token) and len(token) >= 4:
            rows.extend(token[index : index + 2] for index in range(len(token) - 1))
        if len(rows) >= limit * 2:
            break
    return _dedupe_strings(rows, limit=limit)


def _cross_encoder_pair_score(source: object, *, query_terms: list[str], query_text: str) -> float:
    text = _source_text(source).lower()
    title = _source_title(source).lower()
    if not text:
        return 0.0
    matched_terms = [term for term in query_terms if term and term in text]
    title_terms = [term for term in query_terms if term and term in title]
    score = float(len(matched_terms) * 9 + len(title_terms) * 5)
    normalized_query = normalize_text(query_text).lower()
    if normalized_query and normalized_query in text:
        score += 18.0
    if _source_tier(source) == "official":
        score += 10.0
    if any(term in text for term in _PROCUREMENT_TERMS):
        score += 7.0
    if any(term.lower() in text for term in _SOLUTION_TERMS):
        score += 5.0
    excerpt_length = len(normalize_text(str(getattr(source, "excerpt", "") or getattr(source, "snippet", "") or "")))
    if excerpt_length >= 220:
        score += 4.0
    if excerpt_length < 80:
        score -= 5.0
    if any(token in text for token in ("无关", "不相关", "未涉及", "不涉及")) and _source_tier(source) != "official":
        score -= 18.0
    return score


@lru_cache(maxsize=2)
def _load_sentence_transformers_cross_encoder(
    model_name: str,
    cache_dir: str | None = None,
    device: str = "auto",
) -> Any:
    from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

    kwargs: dict[str, Any] = {}
    # Do not let a request-triggered reranker download arbitrary model weights.
    # The caller records an unavailable model as a gate failure and can retry
    # after the explicitly managed cache is present.
    kwargs["local_files_only"] = True
    if cache_dir:
        resolved_cache = Path(cache_dir).expanduser()
        resolved_cache.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HUB_CACHE"] = str(resolved_cache)
        kwargs["cache_folder"] = str(resolved_cache)
    if device and device != "auto":
        kwargs["device"] = device
    return CrossEncoder(model_name, **kwargs)


def _predict_sentence_transformers_scores(
    sources: list[object],
    *,
    query: str,
    model_name: str,
    cache_dir: str | None = None,
    device: str = "auto",
) -> tuple[list[float], str]:
    model = (
        _load_sentence_transformers_cross_encoder(model_name, cache_dir, device)
        if cache_dir or device != "auto"
        else _load_sentence_transformers_cross_encoder(model_name)
    )
    pairs = [
        [
            normalize_text(query),
            normalize_text("；".join([_source_title(source), _source_text(source)]))[:1800],
        ]
        for source in sources
    ]
    raw_scores = model.predict(pairs)
    if hasattr(raw_scores, "tolist"):
        raw_scores = raw_scores.tolist()
    return [float(item) for item in list(raw_scores)], "sentence-transformers"


def rerank_sources_cross_encoder_style(
    sources: Iterable[object],
    *,
    query: str,
    model_name: str,
    top_k: int = 20,
) -> tuple[list[object], CrossEncoderRerankProfile]:
    candidates = list(sources)
    capped_top_k = max(1, min(int(top_k or 20), 80))
    profile = CrossEncoderRerankProfile(
        enabled=True,
        model_name=normalize_text(model_name) or "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k=capped_top_k,
    )
    if len(candidates) <= 1:
        profile.reranked_count = len(candidates)
        profile.notes.append("候选不足，保持原排序。")
        return candidates, profile

    query_terms = _terms(query, limit=40)
    scored = [
        (source, _cross_encoder_pair_score(source, query_terms=query_terms, query_text=query), index)
        for index, source in enumerate(candidates[:capped_top_k])
    ]
    reranked_top = [
        source
        for source, _score, _index in sorted(
            scored,
            key=lambda item: (
                item[1],
                1 if _source_tier(item[0]) == "official" else 0,
                -item[2],
            ),
            reverse=True,
        )
    ]
    profile.reranked_count = len(reranked_top)
    profile.notes.append(f"已对 top {len(reranked_top)} 来源执行本地 cross-encoder-style 相关性复排。")
    return [*reranked_top, *candidates[capped_top_k:]], profile


def rerank_sources_cross_encoder(
    sources: Iterable[object],
    *,
    query: str,
    model_name: str,
    top_k: int = 20,
    backend: str = "auto",
    cache_dir: str | None = None,
    device: str = "auto",
) -> tuple[list[object], CrossEncoderRerankProfile]:
    candidates = list(sources)
    capped_top_k = max(1, min(int(top_k or 20), 80))
    normalized_backend = normalize_text(backend).lower() or "auto"
    resolved_model = normalize_text(model_name) or "cross-encoder/ms-marco-MiniLM-L-6-v2"
    if normalized_backend not in {"auto", "sentence_transformers", "sentence-transformers", "local"}:
        normalized_backend = "auto"

    if normalized_backend != "local" and len(candidates) > 1:
        profile = CrossEncoderRerankProfile(
            enabled=True,
            model_name=resolved_model,
            top_k=capped_top_k,
            backend="sentence-transformers",
        )
        try:
            scored_sources = candidates[:capped_top_k]
            scores, backend_name = _predict_sentence_transformers_scores(
                scored_sources,
                query=query,
                model_name=resolved_model,
                cache_dir=cache_dir,
                device=device,
            )
            if len(scores) != len(scored_sources):
                raise RuntimeError(
                    f"sentence-transformers returned {len(scores)} scores for {len(scored_sources)} source pairs"
                )
            ranked = [
                source
                for source, _score, _index in sorted(
                    zip(scored_sources, scores, range(len(scored_sources)), strict=False),
                    key=lambda item: (item[1], 1 if _source_tier(item[0]) == "official" else 0, -item[2]),
                    reverse=True,
                )
            ]
            profile.backend = backend_name
            profile.reranked_count = len(ranked)
            profile.notes.append(f"已使用 {backend_name} CrossEncoder 对 top {len(ranked)} 来源复排。")
            return [*ranked, *candidates[capped_top_k:]], profile
        except Exception as exc:
            if normalized_backend in {"sentence_transformers", "sentence-transformers"}:
                profile.notes.append(f"sentence-transformers CrossEncoder 加载或预测失败：{exc}")
                return candidates, profile
            fallback, fallback_profile = rerank_sources_cross_encoder_style(
                candidates,
                query=query,
                model_name=resolved_model,
                top_k=capped_top_k,
            )
            fallback_profile.notes.insert(0, f"sentence-transformers 不可用，已回退本地复排：{exc}")
            return fallback, fallback_profile

    return rerank_sources_cross_encoder_style(
        candidates,
        query=query,
        model_name=resolved_model,
        top_k=capped_top_k,
    )


def _source_text(source: object) -> str:
    return normalize_text(
        "；".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "excerpt", "") or ""),
                str(getattr(source, "search_query", "") or ""),
                str(getattr(source, "source_label", "") or ""),
                str(getattr(source, "source_type", "") or ""),
                str(getattr(source, "domain", "") or ""),
            ]
        )
    )


def _source_title(source: object) -> str:
    return normalize_text(str(getattr(source, "title", "") or getattr(source, "url", "") or "未命名来源"))


def _source_url(source: object) -> str:
    return normalize_text(str(getattr(source, "url", "") or ""))


def _source_tier(source: object) -> str:
    tier = normalize_text(str(getattr(source, "source_tier", "") or "")).lower()
    if tier:
        return tier
    text = _source_text(source).lower()
    return "official" if any(hint in text for hint in _OFFICIAL_HINTS) else "media"


def _scope_terms(scope_hints: dict[str, object]) -> list[str]:
    values: list[object] = []
    for key in (
        "regions",
        "industries",
        "clients",
        "company_anchors",
        "must_include_terms",
        "strategy_query_expansions",
    ):
        raw = scope_hints.get(key, [])
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.append(raw)
    return _dedupe_strings(values, limit=24)


def _is_official_source(source: object, source_text: str) -> bool:
    if _source_tier(source) == "official":
        return True
    lowered = source_text.lower()
    return any(hint in lowered for hint in _OFFICIAL_HINTS)


def _score_source(
    source: object,
    *,
    keyword_terms: list[str],
    focus_terms: list[str],
    scope_terms: list[str],
) -> CragSourceGrade:
    text = _source_text(source)
    lowered = text.lower()
    matched_keyword_terms = [term for term in keyword_terms if term in lowered]
    matched_focus_terms = [term for term in focus_terms if term in lowered]
    matched_scope_terms = [term.lower() for term in scope_terms if normalize_text(term).lower() in lowered]
    matched_terms = _dedupe_strings([*matched_keyword_terms, *matched_focus_terms, *matched_scope_terms], limit=12)

    score = 0
    score += min(36, len(matched_keyword_terms) * 12)
    score += min(24, len(matched_focus_terms) * 8)
    score += min(18, len(matched_scope_terms) * 6)
    if _is_official_source(source, text):
        score += 10
    if any(term in text for term in _PROCUREMENT_TERMS):
        score += 8
    if any(term.lower() in lowered for term in _SOLUTION_TERMS):
        score += 6
    if len(normalize_text(str(getattr(source, "excerpt", "") or getattr(source, "snippet", "") or ""))) >= 120:
        score += 4
    if any(token in text for token in ("无关", "不相关", "未涉及", "不涉及", "非本主题")) and not _is_official_source(source, text):
        score -= 22
    score = max(0, min(100, score))

    required_terms = _dedupe_strings([*keyword_terms[:4], *focus_terms[:4], *[term.lower() for term in scope_terms[:4]]], limit=10)
    missing_terms = [term for term in required_terms if term not in matched_terms][:6]
    reasons: list[str] = []
    if matched_keyword_terms:
        reasons.append("命中主题词")
    if matched_focus_terms:
        reasons.append("命中关注点")
    if matched_scope_terms:
        reasons.append("命中范围约束")
    if _is_official_source(source, text):
        reasons.append("官方或准官方来源")
    if any(term in text for term in _PROCUREMENT_TERMS):
        reasons.append("包含招采/预算信号")
    if not reasons:
        reasons.append("未命中主要主题")

    if score >= 55:
        status: Literal["accepted", "ambiguous", "rejected"] = "accepted"
    elif score >= 30:
        status = "ambiguous"
    else:
        status = "rejected"

    return CragSourceGrade(
        title=_source_title(source),
        url=_source_url(source),
        status=status,
        relevance_score=score,
        source_tier=_source_tier(source),
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        reasons=reasons[:4],
    )


def _build_corrective_queries(
    *,
    keyword: str,
    research_focus: str | None,
    scope_terms: list[str],
    missing_terms: list[str],
    limit: int,
) -> list[str]:
    compact_scope_terms = [term for term in scope_terms if 2 <= len(normalize_text(term)) <= 18]
    keyword_seed = normalize_text(keyword)
    focus_seed = normalize_text(research_focus or "")
    if len(keyword_seed) > 24 and any(marker in keyword_seed for marker in ("调研", "研究", "分析", "搜集", "情报")):
        keyword_seed = ""
    if len(focus_seed) > 24:
        focus_seed = ""
    base_parts = _dedupe_strings([*compact_scope_terms[:4], keyword_seed, focus_seed], limit=6)
    base_query = normalize_text(" ".join(base_parts)) or normalize_text(keyword)
    missing = normalize_text(
        " ".join(
            [term for term in missing_terms if 2 <= len(normalize_text(term)) <= 12][:4]
        )
    )
    queries = [
        f"{base_query} 官方 招标 中标 预算",
        f"site:gov.cn {base_query} 政策 规划 预算",
        f"site:ccgp.gov.cn {base_query} 采购意向 招标 中标",
        f"site:ggzy.gov.cn {base_query} 公共资源交易 招标 中标",
        f"{base_query} 产品清单 技术参数 解决方案",
        f"{base_query} 竞品 标杆案例 集成商",
    ]
    if missing:
        queries.insert(1, f"{base_query} {missing} 公开来源")
    return _dedupe_strings(queries, limit=limit)


def _compress_source_context(source: object, grade: CragSourceGrade) -> str:
    text = _source_text(source)
    snippet = normalize_text(getattr(source, "snippet", "") or getattr(source, "excerpt", "") or text)
    if len(snippet) > 180:
        snippet = f"{snippet[:179].rstrip()}…"
    return f"[{grade.source_tier}/{grade.relevance_score}] {grade.title}: {snippet}"


def build_retrieval_correction_profile(
    sources: Iterable[object],
    *,
    keyword: str,
    research_focus: str | None = None,
    scope_hints: dict[str, object] | None = None,
    query_plan: Iterable[str] | None = None,
    corrective_query_limit: int = 6,
) -> RetrievalCorrectionProfile:
    source_list = list(sources)
    scope_hints = scope_hints or {}
    keyword_terms = _terms(keyword, limit=16)
    focus_terms = _terms(research_focus or "", limit=18)
    scoped_terms = _scope_terms(scope_hints)

    grades = [
        _score_source(
            source,
            keyword_terms=keyword_terms,
            focus_terms=focus_terms,
            scope_terms=scoped_terms,
        )
        for source in source_list
    ]
    accepted = [grade for grade in grades if grade.status == "accepted"]
    ambiguous = [grade for grade in grades if grade.status == "ambiguous"]
    rejected = [grade for grade in grades if grade.status == "rejected"]
    useful_grades = accepted or ambiguous
    relevance_score = round(sum(grade.relevance_score for grade in useful_grades) / len(useful_grades)) if useful_grades else 0
    missing_terms = _dedupe_strings((term for grade in grades for term in grade.missing_terms), limit=12)
    corrective_queries = _build_corrective_queries(
        keyword=keyword,
        research_focus=research_focus,
        scope_terms=scoped_terms,
        missing_terms=missing_terms,
        limit=corrective_query_limit,
    )
    existing_queries = {normalize_text(str(query)).lower() for query in query_plan or []}
    corrective_queries = [query for query in corrective_queries if normalize_text(query).lower() not in existing_queries]

    if not source_list or len(accepted) == 0:
        status: Literal["ready", "needs_filtering", "needs_expansion"] = "needs_expansion"
    elif len(accepted) < 3 and relevance_score < 58:
        status = "needs_expansion"
    elif rejected and len(rejected) >= max(2, len(source_list) // 3):
        status = "needs_filtering"
    else:
        status = "ready"

    source_by_url = {_source_url(source): source for source in source_list}
    compressed_context = []
    for grade in sorted(grades, key=lambda item: item.relevance_score, reverse=True):
        if grade.status == "rejected":
            continue
        source = source_by_url.get(grade.url)
        if source is None:
            continue
        compressed_context.append(_compress_source_context(source, grade))
        if len(compressed_context) >= 8:
            break

    review_notes = [
        f"来源评分：可用 {len(accepted)} 条，需复核 {len(ambiguous)} 条，建议剔除 {len(rejected)} 条。",
        f"平均相关度 {relevance_score}/100。",
    ]
    if status == "needs_expansion":
        review_notes.append("可用来源不足，建议先用重写后的查询补充官方、招采和产品技术来源。")
    elif status == "needs_filtering":
        review_notes.append("存在较多弱相关来源，生成时只把高相关来源作为强依据。")

    return RetrievalCorrectionProfile(
        status=status,
        relevance_score=relevance_score,
        accepted_source_count=len(accepted),
        ambiguous_source_count=len(ambiguous),
        rejected_source_count=len(rejected),
        grades=grades,
        corrective_queries=corrective_queries,
        compressed_context=compressed_context,
        review_notes=review_notes,
    )


def render_retrieval_correction_context(profile: RetrievalCorrectionProfile) -> str:
    lines = [
        f"CRAG来源校正状态: {profile.status}",
        f"相关度: {profile.relevance_score}/100；可用来源 {profile.accepted_source_count}；需复核 {profile.ambiguous_source_count}；弱相关 {profile.rejected_source_count}",
    ]
    if profile.review_notes:
        lines.append("校正结论: " + "；".join(profile.review_notes))
    if profile.corrective_queries:
        lines.append("建议补充查询: " + " | ".join(profile.corrective_queries[:6]))
    if profile.compressed_context:
        lines.append("高相关来源压缩上下文:")
        lines.extend(f"- {item}" for item in profile.compressed_context[:8])
    return "\n".join(lines)


def _claim_rows(report: object) -> list[str]:
    rows: list[str] = []
    for value in (
        getattr(report, "report_title", ""),
        getattr(report, "executive_summary", ""),
        getattr(report, "consulting_angle", ""),
    ):
        rows.extend(_SENTENCE_SPLIT_RE.split(normalize_text(str(value or ""))))

    for field_name in (
        "target_accounts",
        "target_departments",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "ecosystem_partners",
        "competitor_profiles",
        "benchmark_cases",
        "flagship_products",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
    ):
        values = getattr(report, field_name, []) or []
        if isinstance(values, list):
            rows.extend(normalize_text(str(item or "")) for item in values)
    for section in getattr(report, "sections", []) or []:
        rows.append(normalize_text(str(getattr(section, "title", "") or "")))
        rows.extend(normalize_text(str(item or "")) for item in (getattr(section, "items", []) or []))
    return [row for row in _dedupe_strings(rows, limit=80) if len(row) >= 6]


def _claim_supported(claim: str, source_corpus: str) -> bool:
    claim_terms = [term for term in _terms(claim, limit=16) if len(term) >= 2]
    if not claim_terms:
        return False
    direct_hits = [term for term in claim_terms if term in source_corpus]
    if len(direct_hits) >= 2:
        return True
    if any(term in claim for term in _PROCUREMENT_TERMS) and any(term in source_corpus for term in _PROCUREMENT_TERMS):
        return bool(direct_hits)
    return len(direct_hits) >= max(1, min(3, len(claim_terms) // 3))


def review_generation_grounding(report: object, sources: Iterable[object]) -> GenerationGroundingReview:
    source_list = list(sources)
    source_corpus = normalize_text("；".join(_source_text(source) for source in source_list)).lower()
    claims = _claim_rows(report)
    if not claims or not source_corpus:
        return GenerationGroundingReview(
            grounding_score=0,
            response_quality_score=0,
            unsupported_claims=claims[:8],
            review_notes=["缺少可校验的来源或结论，无法完成生成后校验。"],
        )

    supported: list[str] = []
    unsupported: list[str] = []
    for claim in claims:
        if _claim_supported(claim.lower(), source_corpus):
            supported.append(claim)
        else:
            unsupported.append(claim)
        if len(supported) >= 16 and len(unsupported) >= 8:
            break

    total = max(1, len(supported) + len(unsupported))
    grounding_score = round((len(supported) / total) * 100)
    actionability_hits = sum(1 for claim in claims if any(term in claim for term in _ACTION_TERMS))
    solution_hits = sum(1 for claim in claims if any(term in claim for term in _SOLUTION_TERMS))
    response_quality_score = round(min(100, grounding_score * 0.72 + min(actionability_hits, 8) * 2.2 + min(solution_hits, 8) * 1.8))

    notes = [f"生成后校验覆盖 {total} 条核心结论，{len(supported)} 条有来源词项支撑。"]
    if unsupported:
        notes.append("未支撑结论需要降调或补来源后再用于正式材料。")

    return GenerationGroundingReview(
        grounding_score=grounding_score,
        response_quality_score=response_quality_score,
        supported_claims=supported[:10],
        unsupported_claims=unsupported[:10],
        review_notes=notes,
    )
