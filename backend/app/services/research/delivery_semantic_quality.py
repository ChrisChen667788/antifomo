from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.services.content_extractor import normalize_text
from app.services.research.source_documents import looks_like_source_artifact_text


_DELIVERY_NOISE_TOKENS = (
    "返回顶部",
    "跳转到主要内容",
    "当前位置",
    "网站首页",
    "首页 关于我们",
    "关注我们",
    "扫码关注",
    "微信公众号 扫码",
    "登录 注册",
    "客服中心 隐私声明",
    "免责声明",
    "相关阅读",
    "上一篇",
    "下一篇",
    "点击查看原文",
    "阅读原文",
    "报告共计：",
    "文章标签：",
)

_STRONG_CLAIM_PATTERN = re.compile(
    r"(?:"
    r"\d+(?:\.\d+)?\s*(?:%|％|万元|亿元|万|亿|年|个月|月|天|家|项|条|倍|套|路)"
    r"|预算(?:金额)?"
    r"|中标(?:金额)?"
    r"|采购金额"
    r"|同比(?:增长|下降)?"
    r"|市场份额"
    r"|覆盖率"
    r"|节省"
    r"|提升"
    r"|降低"
    r"|回收期"
    r"|内部收益率"
    r"|净现值"
    r")",
    re.IGNORECASE,
)

_TRACEABILITY_PATTERNS = (
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"(?:来源|证据|依据)[:：]\s*\S+"),
    re.compile(r"(?:项目|采购|招标|合同|公告)(?:编号|编码)[:：]?\s*[A-Za-z0-9][A-Za-z0-9._/-]{3,}"),
    re.compile(r"\[(?:S|E|SRC|证据)\s*[-_#]?\s*\d+\]", re.IGNORECASE),
    re.compile(r"(?:chunk|source)[-_ ]?id[:：=]\s*[A-Za-z0-9._/-]+", re.IGNORECASE),
    re.compile(r"根据《[^》]{2,80}》"),
)


@dataclass(frozen=True, slots=True)
class DeliverySemanticAudit:
    content_hygiene_score: int
    traceability_score: int
    hard_score_cap: int
    noise_rows: tuple[str, ...]
    strong_claim_rows: tuple[str, ...]
    untraceable_claim_rows: tuple[str, ...]
    traceable_anchor_count: int


def _dedupe_rows(values: Iterable[object], *, limit: int = 80) -> list[str]:
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


def _looks_like_delivery_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if looks_like_source_artifact_text(normalized):
        return True
    return any(token.lower() in normalized.lower() for token in _DELIVERY_NOISE_TOKENS)


def _traceable_anchor_count(value: str) -> int:
    return sum(1 for pattern in _TRACEABILITY_PATTERNS if pattern.search(value))


def audit_delivery_semantics(
    rows: Iterable[object],
    *,
    source_support_score: int,
    grounded_count: int,
    evidence_note_count: int,
) -> DeliverySemanticAudit:
    normalized_rows = _dedupe_rows(rows)
    noise_rows = [row for row in normalized_rows if _looks_like_delivery_noise(row)]
    strong_claim_rows = [row for row in normalized_rows if _STRONG_CLAIM_PATTERN.search(row)]
    anchor_counts = {row: _traceable_anchor_count(row) for row in normalized_rows}
    traceable_anchor_count = sum(anchor_counts.values())
    untraceable_claim_rows = [row for row in strong_claim_rows if anchor_counts.get(row, 0) <= 0]

    content_hygiene_score = max(
        0,
        100
        - min(90, len(noise_rows) * 34)
        - (12 if len(noise_rows) >= 2 else 0),
    )

    support_component = min(42, max(0, int(source_support_score or 0)) * 0.46)
    process_component = min(14, max(0, int(grounded_count or 0)) * 3.5)
    evidence_component = min(10, max(0, int(evidence_note_count or 0)) * 2)
    claim_coverage = (
        (len(strong_claim_rows) - len(untraceable_claim_rows)) / len(strong_claim_rows)
        if strong_claim_rows
        else 0.0
    )
    traceability_score = round(
        min(
            100,
            18
            + support_component
            + process_component
            + evidence_component
            + min(20, traceable_anchor_count * 5)
            + round(claim_coverage * 16),
        )
    )

    # A chapter named "证据矩阵" is not itself evidence. Until at least one
    # concrete source/document/chunk anchor is present, this dimension cannot
    # pass and the overall delivery profile cannot be labeled pass.
    if traceable_anchor_count <= 0:
        traceability_score = min(traceability_score, 72)
    if strong_claim_rows and untraceable_claim_rows:
        traceability_score = min(
            traceability_score,
            max(20, 76 - round(44 * len(untraceable_claim_rows) / len(strong_claim_rows))),
        )

    hard_score_cap = 100
    if noise_rows:
        hard_score_cap = 62 if len(noise_rows) >= 2 else 67
    elif traceability_score < 61:
        hard_score_cap = 67
    elif traceability_score < 75:
        hard_score_cap = 83

    return DeliverySemanticAudit(
        content_hygiene_score=content_hygiene_score,
        traceability_score=traceability_score,
        hard_score_cap=hard_score_cap,
        noise_rows=tuple(noise_rows[:5]),
        strong_claim_rows=tuple(strong_claim_rows[:8]),
        untraceable_claim_rows=tuple(untraceable_claim_rows[:5]),
        traceable_anchor_count=traceable_anchor_count,
    )
