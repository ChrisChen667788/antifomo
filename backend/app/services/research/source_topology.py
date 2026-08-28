from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Literal
from urllib.parse import urlparse

from app.schemas.research import ResearchScopeContractOut
from app.services.content_extractor import normalize_text
from app.services.research.entity_authenticity_gate import source_has_target_role_evidence
from app.services.research.scope_hints import REGION_SCOPE_ALIASES
from app.services.research.source_documents import SourceDocument, source_document_text


SourceTopologyClass = Literal[
    "local_target_proof",
    "local_comparable",
    "external_benchmark",
    "policy_context",
    "historical_context",
    "unqualified",
]
EvidenceLane = Literal["decision", "benchmark", "context", "rejected"]


_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?:年|年度|[-/.]\d{1,2})?")
_PROCUREMENT_TERMS = ("采购意向", "采购人", "招标", "中标", "成交", "预算", "建设单位", "业主单位")
_POLICY_TERMS = ("政策", "规划", "行动计划", "指导意见", "通知", "工作方案", "实施方案")
_UNSAFE_HOSTS = ("google.com", "baidu.com", "bing.com", "sogou.com", "so.com")
_UNSAFE_URL_MARKERS = ("javascript:", "redirect", "url=", "cache/", "/search?")


@dataclass(frozen=True, slots=True)
class SourceTopologyAssessment:
    source_topology: SourceTopologyClass
    evidence_lane: EvidenceLane
    local_scope_match: bool
    current_signal: bool
    primary_origin: bool
    url_safe: bool
    snapshot_or_reused: bool
    formal_claim_eligible: bool
    account_pursuit_eligible: bool
    reasons: tuple[str, ...]

    def as_admission_fields(self) -> dict[str, object]:
        return {
            "source_topology": self.source_topology,
            "evidence_lane": self.evidence_lane,
            "local_scope_match": self.local_scope_match,
            "current_signal": self.current_signal,
            "primary_origin": self.primary_origin,
            "url_safe": self.url_safe,
            "snapshot_or_reused": self.snapshot_or_reused,
            "formal_claim_eligible": self.formal_claim_eligible,
            "account_pursuit_eligible": self.account_pursuit_eligible,
        }


def _source_text(source: SourceDocument) -> str:
    return normalize_text(
        " ".join(
            [
                source_document_text(source),
                source.domain or "",
                source.url or "",
            ]
        )
    ).casefold()


def _region_terms(contract: ResearchScopeContractOut) -> tuple[str, ...]:
    values: list[str] = []
    for region in contract.regions:
        normalized = normalize_text(region)
        if not normalized:
            continue
        values.append(normalized)
        values.extend(REGION_SCOPE_ALIASES.get(normalized, ()))
    return tuple(dict.fromkeys(value.casefold() for value in values if value))


def _is_local_source(source: SourceDocument, contract: ResearchScopeContractOut) -> bool:
    if not contract.regions and not contract.clients:
        return True
    text = _source_text(source)
    if any(term in text for term in _region_terms(contract)):
        return True
    return any(normalize_text(client).casefold() in text for client in contract.clients if normalize_text(client))


def _year_signal(source: SourceDocument, *, now: datetime) -> tuple[bool, bool]:
    text = normalize_text(" ".join([source.title, source.snippet, source.excerpt]))
    years = [int(value) for value in _YEAR_RE.findall(text)]
    if not years:
        return True, False
    latest_year = max(years)
    return latest_year >= now.year - 2, latest_year < now.year - 2


def _is_url_safe(source: SourceDocument) -> bool:
    parsed = urlparse(source.url)
    hostname = normalize_text(parsed.hostname or "").casefold().removeprefix("www.")
    path_and_query = normalize_text(f"{parsed.path}?{parsed.query}").casefold()
    if parsed.scheme not in {"http", "https"} or not hostname:
        return False
    if any(hostname == blocked or hostname.endswith(f".{blocked}") for blocked in _UNSAFE_HOSTS):
        return False
    return not any(marker in path_and_query or marker in source.url.casefold() for marker in _UNSAFE_URL_MARKERS)


def assess_source_topology(
    source: SourceDocument,
    *,
    contract: ResearchScopeContractOut,
    scope_hints: dict[str, object],
    now: datetime | None = None,
) -> SourceTopologyAssessment:
    """Classify evidence by its permitted use, before ranking or report writing."""

    now = now or datetime.now(timezone.utc)
    text = _source_text(source)
    url_safe = _is_url_safe(source)
    snapshot_or_reused = normalize_text(source.source_origin).casefold() == "snapshot_cache"
    current_signal, explicitly_historical = _year_signal(source, now=now)
    local_scope_match = _is_local_source(source, contract)
    primary_origin = source.source_tier == "official"
    has_target_role = source_has_target_role_evidence(source, scope_hints=scope_hints)
    has_procurement_signal = any(term.casefold() in text for term in _PROCUREMENT_TERMS)
    has_policy_signal = source.source_type == "policy" or any(term.casefold() in text for term in _POLICY_TERMS)
    reasons: list[str] = []

    if not url_safe:
        return SourceTopologyAssessment(
            source_topology="unqualified",
            evidence_lane="rejected",
            local_scope_match=local_scope_match,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=False,
            snapshot_or_reused=snapshot_or_reused,
            formal_claim_eligible=False,
            account_pursuit_eligible=False,
            reasons=("URL is a search/redirect/unsafe endpoint and cannot be evidence.",),
        )
    if not text:
        return SourceTopologyAssessment(
            source_topology="unqualified",
            evidence_lane="rejected",
            local_scope_match=local_scope_match,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=snapshot_or_reused,
            formal_claim_eligible=False,
            account_pursuit_eligible=False,
            reasons=("Source has no extractable evidence text.",),
        )
    if snapshot_or_reused or explicitly_historical:
        reasons.append("Snapshot-reused or explicitly historical evidence is context only.")
        return SourceTopologyAssessment(
            source_topology="historical_context",
            evidence_lane="context",
            local_scope_match=local_scope_match,
            current_signal=False,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=snapshot_or_reused,
            formal_claim_eligible=False,
            account_pursuit_eligible=False,
            reasons=tuple(reasons),
        )
    if has_target_role and has_procurement_signal and local_scope_match:
        reasons.append("Local buyer/owner role and procurement signal are present.")
        return SourceTopologyAssessment(
            source_topology="local_target_proof",
            evidence_lane="decision",
            local_scope_match=True,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=True,
            account_pursuit_eligible=current_signal and primary_origin,
            reasons=tuple(reasons),
        )
    if local_scope_match and has_target_role:
        reasons.append("Local buyer/owner role is present; procurement stage still needs confirmation.")
        return SourceTopologyAssessment(
            source_topology="local_target_proof",
            evidence_lane="decision",
            local_scope_match=True,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=True,
            account_pursuit_eligible=current_signal and primary_origin,
            reasons=tuple(reasons),
        )
    if has_procurement_signal and local_scope_match:
        reasons.append("Local procurement signal supports a comparable opportunity, but the named buyer is not yet verified.")
        return SourceTopologyAssessment(
            source_topology="local_comparable",
            evidence_lane="decision",
            local_scope_match=True,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=current_signal,
            account_pursuit_eligible=False,
            reasons=tuple(reasons),
        )
    if has_target_role or has_procurement_signal:
        reasons.append("Buyer/procurement signal is outside the requested locality and is benchmark-only.")
        return SourceTopologyAssessment(
            source_topology="external_benchmark",
            evidence_lane="benchmark",
            local_scope_match=False,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=False,
            account_pursuit_eligible=False,
            reasons=tuple(reasons),
        )
    if has_policy_signal and primary_origin:
        reasons.append("Official policy may support market context, not a named account opportunity.")
        return SourceTopologyAssessment(
            source_topology="policy_context",
            evidence_lane="context",
            local_scope_match=local_scope_match,
            current_signal=current_signal,
            primary_origin=True,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=current_signal,
            account_pursuit_eligible=False,
            reasons=tuple(reasons),
        )
    if local_scope_match:
        reasons.append("Local comparable evidence supports a market scan, not a named buyer assertion.")
        return SourceTopologyAssessment(
            source_topology="local_comparable",
            evidence_lane="decision",
            local_scope_match=True,
            current_signal=current_signal,
            primary_origin=primary_origin,
            url_safe=True,
            snapshot_or_reused=False,
            formal_claim_eligible=current_signal,
            account_pursuit_eligible=False,
            reasons=tuple(reasons),
        )
    reasons.append("The source may be useful as an external benchmark only.")
    return SourceTopologyAssessment(
        source_topology="external_benchmark",
        evidence_lane="benchmark",
        local_scope_match=False,
        current_signal=current_signal,
        primary_origin=primary_origin,
        url_safe=True,
        snapshot_or_reused=False,
        formal_claim_eligible=False,
        account_pursuit_eligible=False,
        reasons=tuple(reasons),
    )


def topology_counts(assessments: list[SourceTopologyAssessment]) -> dict[str, int]:
    counts = {key: 0 for key in (
        "local_target_proof",
        "local_comparable",
        "external_benchmark",
        "policy_context",
        "historical_context",
        "unqualified",
    )}
    for assessment in assessments:
        counts[assessment.source_topology] = counts.get(assessment.source_topology, 0) + 1
    return counts
