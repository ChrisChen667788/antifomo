from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from app.schemas.research import (
    ResearchEntityAuthenticityGateOut,
    ResearchEntityGraphOut,
    ResearchNormalizedEntityOut,
    ResearchRankedEntityOut,
    ResearchReportResponse,
)
from app.services.content_extractor import normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.entity_authenticity import evaluate_organization_name
from app.services.research.entity_policy import KNOWN_LIGHTWEIGHT_ENTITY_NAMES, SPECIAL_ENTITY_ALIASES
from app.services.research.organization_identity import (
    entity_canonical_key,
    extract_rank_entity_candidates,
    org_surface_variants,
    resolve_known_org_name,
    scope_org_names,
    source_mentions_entity,
)
from app.services.research.scope_hints import REGION_SCOPE_ALIASES
from app.services.research.source_documents import SourceDocument, source_document_text


_TARGET_ROLE_PREFIX_PATTERN = re.compile(
    r"(?:采购人(?:信息)?|招标人|业主单位|建设单位|需求方|甲方|出资方|投资方|主管部门)"
    r".{0,16}$"
)
_TARGET_ROLE_SUFFIX_PATTERN = re.compile(
    r"^(?:作为(?:采购人|招标人|业主|建设单位)|指导并负责|牵头|负责|统筹|采购|招标|建设|运营|部署|委托|实施|出资|投资|"
    r"关于.{0,48}(?:采购|招标|项目)|"
    r"推进.{0,24}(?:项目|系统|平台|建设|运营|试点)|.{0,12}发布.{0,24}(?:采购意向|招标公告|采购公告))"
)


REPORT_ENTITY_FIELDS = (
    "target_accounts",
    "competitor_profiles",
    "ecosystem_partners",
)
REPORT_ENTITY_CONTEXT_FIELDS = (
    "client_peer_moves",
    "winner_peer_moves",
)
TRUSTED_ENTITY_NAMES = tuple(
    dict.fromkeys((*KNOWN_LIGHTWEIGHT_ENTITY_NAMES, *SPECIAL_ENTITY_ALIASES))
)


@dataclass(frozen=True, slots=True)
class EntityAuthenticityAudit:
    checked_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    repaired_count: int = 0
    unsupported_count: int = 0
    rejected_samples: tuple[str, ...] = ()
    repair_samples: tuple[str, ...] = ()
    rejected_values: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "checked_count": self.checked_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "repaired_count": self.repaired_count,
            "unsupported_count": self.unsupported_count,
            "rejected_samples": list(self.rejected_samples),
            "repair_samples": list(self.repair_samples),
            "rejected_values": list(self.rejected_values),
        }


class EntityAuthenticityGateError(RuntimeError):
    pass


def _dedupe(values: Iterable[str], *, limit: int = 24) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def _scope_known_names(scope_hints: dict[str, object] | None) -> tuple[str, ...]:
    return tuple(
        _dedupe(
            [
                *KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
                *SPECIAL_ENTITY_ALIASES,
                *scope_org_names(scope_hints),
            ],
            limit=96,
        )
    )


def _source_supports_candidate(
    candidate: str,
    *,
    sources: list[SourceDocument],
) -> bool:
    return any(source_mentions_entity(source, candidate) for source in sources)


def source_supports_target_role(
    candidate: str,
    *,
    sources: list[SourceDocument],
) -> bool:
    variants = org_surface_variants(candidate)
    for source in sources:
        text = source_document_text(source)
        for sentence in re.split(r"[。！？!?；;\n]", text):
            normalized = normalize_text(sentence)
            for variant in variants:
                start = normalized.find(variant)
                if start < 0:
                    continue
                prefix = normalized[max(0, start - 32) : start]
                suffix = normalized[start + len(variant) : start + len(variant) + 36]
                if _TARGET_ROLE_PREFIX_PATTERN.search(prefix) or _TARGET_ROLE_SUFFIX_PATTERN.search(suffix):
                    return True
    return False


def _source_matches_local_scope(
    source: SourceDocument,
    *,
    scope_hints: dict[str, object] | None,
) -> bool:
    scope = scope_hints or {}
    regions = [normalize_text(str(item)) for item in scope.get("regions", []) or [] if normalize_text(str(item))]
    clients = [normalize_text(str(item)) for item in scope.get("clients", []) or [] if normalize_text(str(item))]
    if not regions and not clients:
        return True
    text = normalize_text(
        " ".join([source_document_text(source), source.domain or "", source.url or ""])
    ).casefold()
    if any(client.casefold() in text for client in clients):
        return True
    aliases = [
        normalize_text(alias).casefold()
        for region in regions
        for alias in (region, *REGION_SCOPE_ALIASES.get(region, ()))
        if normalize_text(alias)
    ]
    return any(alias in text for alias in aliases)


def source_supports_local_target_role(
    candidate: str,
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object] | None,
) -> bool:
    return any(
        _source_matches_local_scope(source, scope_hints=scope_hints)
        and source_supports_target_role(candidate, sources=[source])
        for source in sources
    )


def source_has_target_role_evidence(
    source: SourceDocument,
    *,
    scope_hints: dict[str, object] | None = None,
) -> bool:
    known_names = _scope_known_names(scope_hints)
    for extracted in extract_rank_entity_candidates(source_document_text(source), scope_hints=scope_hints):
        canonical = resolve_known_org_name(extracted, scope_hints=scope_hints)
        decision = evaluate_organization_name(
            canonical,
            known_names=known_names,
            trusted_known_names=TRUSTED_ENTITY_NAMES,
        )
        if decision.accepted and source_supports_target_role(decision.normalized_name, sources=[source]):
            return True
    return False


def _sample(field_key: str, value: str, reason: str) -> str:
    normalized = normalize_text(value)
    if len(normalized) > 72:
        normalized = f"{normalized[:71]}…"
    return f"{field_key}: {normalized} ({reason})"


def _sanitize_entity_field_values(
    field_key: str,
    values: Iterable[str],
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object] | None,
    require_source_support: bool,
) -> tuple[list[str], EntityAuthenticityAudit]:
    known_names = _scope_known_names(scope_hints)
    accepted: list[str] = []
    accepted_keys: set[str] = set()
    checked_count = 0
    repaired_count = 0
    unsupported_count = 0
    accepted_row_count = 0
    rejected_samples: list[str] = []
    repair_samples: list[str] = []
    rejected_values: list[str] = []

    for raw_value in values:
        raw = normalize_text(str(raw_value))
        if not raw:
            continue
        checked_count += 1
        candidates = extract_rank_entity_candidates(raw, scope_hints=scope_hints)
        if not candidates:
            decision = evaluate_organization_name(
                raw,
                known_names=known_names,
                trusted_known_names=TRUSTED_ENTITY_NAMES,
            )
            rejected_samples.append(_sample(field_key, raw, decision.reason))
            rejected_values.append(raw)
            continue

        row_accepted = False
        rejected_sample_count = len(rejected_samples)
        for extracted in candidates:
            canonical = resolve_known_org_name(extracted, scope_hints=scope_hints)
            decision = evaluate_organization_name(
                canonical,
                known_names=known_names,
                trusted_known_names=TRUSTED_ENTITY_NAMES,
            )
            if not decision.accepted:
                rejected_samples.append(_sample(field_key, raw, decision.reason))
                continue
            candidate = decision.normalized_name
            if require_source_support and not _source_supports_candidate(
                candidate,
                sources=sources,
            ):
                unsupported_count += 1
                rejected_samples.append(_sample(field_key, raw, "missing_source_support"))
                continue
            explicit_clients = {
                normalize_text(str(item))
                for item in (scope_hints or {}).get("clients", []) or []
                if normalize_text(str(item))
            }
            if (
                field_key == "target_accounts"
                and candidate not in explicit_clients
                and not source_supports_local_target_role(
                    candidate,
                    sources=sources,
                    scope_hints=scope_hints,
                )
            ):
                unsupported_count += 1
                rejected_samples.append(_sample(field_key, raw, "missing_target_role_support"))
                continue
            canonical_key = entity_canonical_key(candidate) or candidate.lower()
            if canonical_key in accepted_keys:
                row_accepted = True
                continue
            accepted_keys.add(canonical_key)
            accepted.append(candidate)
            row_accepted = True
            if candidate != raw:
                repaired_count += 1
                repair_samples.append(f"{field_key}: {raw[:56]} -> {candidate}")
        if not row_accepted:
            rejected_values.append(raw)
            if len(rejected_samples) == rejected_sample_count:
                rejected_samples.append(_sample(field_key, raw, "no_authentic_entity"))
        if row_accepted:
            accepted_row_count += 1

    return accepted, EntityAuthenticityAudit(
        checked_count=checked_count,
        accepted_count=len(accepted),
        rejected_count=checked_count - accepted_row_count,
        repaired_count=repaired_count,
        unsupported_count=unsupported_count,
        rejected_samples=tuple(_dedupe(rejected_samples, limit=8)),
        repair_samples=tuple(_dedupe(repair_samples, limit=8)),
        rejected_values=tuple(_dedupe(rejected_values, limit=24)),
    )


def _sanitize_entity_context_values(
    field_key: str,
    values: Iterable[str],
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object] | None,
) -> tuple[list[str], EntityAuthenticityAudit]:
    known_names = _scope_known_names(scope_hints)
    accepted: list[str] = []
    rejected_samples: list[str] = []
    unsupported_count = 0
    checked_count = 0

    for raw_value in values:
        raw = normalize_text(str(raw_value))
        if not raw:
            continue
        checked_count += 1
        candidates = extract_rank_entity_candidates(raw, scope_hints=scope_hints)
        authentic_candidates: list[str] = []
        supported_candidates: list[str] = []
        for extracted in candidates:
            canonical = resolve_known_org_name(extracted, scope_hints=scope_hints)
            decision = evaluate_organization_name(
                canonical,
                known_names=known_names,
                trusted_known_names=TRUSTED_ENTITY_NAMES,
            )
            if not decision.accepted:
                continue
            candidate = decision.normalized_name
            authentic_candidates.append(candidate)
            if _source_supports_candidate(
                candidate,
                sources=sources,
            ):
                supported_candidates.append(candidate)
        if supported_candidates:
            accepted.append(raw)
            continue
        reason = "missing_source_support" if authentic_candidates else "no_authentic_entity"
        if authentic_candidates:
            unsupported_count += 1
        rejected_samples.append(_sample(field_key, raw, reason))

    return _dedupe(accepted), EntityAuthenticityAudit(
        checked_count=checked_count,
        accepted_count=len(accepted),
        rejected_count=checked_count - len(accepted),
        unsupported_count=unsupported_count,
        rejected_samples=tuple(_dedupe(rejected_samples, limit=8)),
    )


def _merge_audits(*audits: EntityAuthenticityAudit) -> EntityAuthenticityAudit:
    return EntityAuthenticityAudit(
        checked_count=sum(item.checked_count for item in audits),
        accepted_count=sum(item.accepted_count for item in audits),
        rejected_count=sum(item.rejected_count for item in audits),
        repaired_count=sum(item.repaired_count for item in audits),
        unsupported_count=sum(item.unsupported_count for item in audits),
        rejected_samples=tuple(_dedupe((sample for item in audits for sample in item.rejected_samples), limit=8)),
        repair_samples=tuple(_dedupe((sample for item in audits for sample in item.repair_samples), limit=8)),
        rejected_values=tuple(_dedupe((value for item in audits for value in item.rejected_values), limit=24)),
    )


def _audit_from_mapping(value: dict[str, object] | None) -> EntityAuthenticityAudit:
    payload = value or {}
    return EntityAuthenticityAudit(
        checked_count=int(payload.get("checked_count", 0) or 0),
        accepted_count=int(payload.get("accepted_count", 0) or 0),
        rejected_count=int(payload.get("rejected_count", 0) or 0),
        repaired_count=int(payload.get("repaired_count", 0) or 0),
        unsupported_count=int(payload.get("unsupported_count", 0) or 0),
        rejected_samples=tuple(str(item) for item in payload.get("rejected_samples", []) or []),
        repair_samples=tuple(str(item) for item in payload.get("repair_samples", []) or []),
        rejected_values=tuple(str(item) for item in payload.get("rejected_values", []) or []),
    )


def _entity_placeholder(output_language: str) -> str:
    if output_language == "en":
        return "unverified organization"
    if output_language == "zh-TW":
        return "待核驗機構"
    return "待核验机构"


def _scrub_rejected_entity_mentions(
    payload: dict[str, object],
    *,
    rejected_values: Iterable[str],
    output_language: str,
) -> None:
    replacement = _entity_placeholder(output_language)
    values = sorted(_dedupe(rejected_values, limit=24), key=len, reverse=True)
    for field_key in ("report_title", "executive_summary", "consulting_angle"):
        text = normalize_text(str(payload.get(field_key, "") or ""))
        for rejected in values:
            if len(rejected) >= 3:
                text = text.replace(rejected, replacement)
        payload[field_key] = normalize_text(text)

    rejected_keys = {normalize_text(value).lower() for value in values if normalize_text(value)}
    key_signals = payload.get("key_signals", [])
    if isinstance(key_signals, list):
        payload["key_signals"] = [
            row
            for row in key_signals
            if normalize_text(str(row)).lower() not in rejected_keys
        ]

    for field_key in (
        "commercial_opportunities",
        "sales_strategy",
        "bidding_strategy",
        "outreach_strategy",
        "ecosystem_strategy",
        "competition_analysis",
        "next_actions",
    ):
        rows = payload.get(field_key, [])
        if not isinstance(rows, list):
            continue
        cleaned_rows: list[object] = []
        for row in rows:
            normalized = normalize_text(str(row))
            entity_label = normalize_text(normalized.split("：", 1)[0].split(":", 1)[0]).lower()
            if entity_label in rejected_keys:
                continue
            cleaned_rows.append(row)
        payload[field_key] = cleaned_rows


def sanitize_report_result_entities(
    parsed: ResearchReportResult,
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object] | None,
    output_language: str = "zh-CN",
    prior_audit: dict[str, object] | None = None,
) -> tuple[ResearchReportResult, dict[str, object]]:
    payload = parsed.model_dump(mode="python")
    audits: list[EntityAuthenticityAudit] = []
    for field_key in REPORT_ENTITY_FIELDS:
        values = payload.get(field_key, [])
        cleaned, audit = _sanitize_entity_field_values(
            field_key,
            values if isinstance(values, list) else [],
            sources=sources,
            scope_hints=scope_hints,
            require_source_support=True,
        )
        payload[field_key] = cleaned
        audits.append(audit)
    for field_key in REPORT_ENTITY_CONTEXT_FIELDS:
        values = payload.get(field_key, [])
        cleaned, audit = _sanitize_entity_context_values(
            field_key,
            values if isinstance(values, list) else [],
            sources=sources,
            scope_hints=scope_hints,
        )
        payload[field_key] = cleaned
        audits.append(audit)
    merged = _merge_audits(_audit_from_mapping(prior_audit), *audits)
    _scrub_rejected_entity_mentions(
        payload,
        rejected_values=merged.rejected_values,
        output_language=output_language,
    )
    return ResearchReportResult.model_validate(payload), merged.as_dict()


def _sanitize_ranked_entities(
    field_key: str,
    values: list[ResearchRankedEntityOut],
    *,
    sources: list[SourceDocument],
    scope_hints: dict[str, object] | None,
) -> tuple[list[ResearchRankedEntityOut], EntityAuthenticityAudit]:
    known_names = _scope_known_names(scope_hints)
    accepted: list[ResearchRankedEntityOut] = []
    rejected: list[str] = []
    rejected_values: list[str] = []
    repaired: list[str] = []
    unsupported_count = 0
    for entity in values:
        decision = evaluate_organization_name(
            entity.name,
            known_names=known_names,
            trusted_known_names=TRUSTED_ENTITY_NAMES,
        )
        if not decision.accepted:
            rejected.append(_sample(field_key, entity.name, decision.reason))
            rejected_values.append(entity.name)
            continue
        candidate = resolve_known_org_name(decision.normalized_name, scope_hints=scope_hints)
        if field_key in {"top_target_accounts", "pending_target_candidates"} and not source_supports_local_target_role(
            candidate,
            sources=sources,
            scope_hints=scope_hints,
        ):
            unsupported_count += 1
            rejected.append(_sample(field_key, entity.name, "missing_local_target_role_support"))
            rejected_values.append(entity.name)
            continue
        has_embedded_evidence = any(normalize_text(link.url) for link in entity.evidence_links)
        if not has_embedded_evidence and not _source_supports_candidate(
            candidate,
            sources=sources,
        ):
            unsupported_count += 1
            rejected.append(_sample(field_key, entity.name, "missing_source_support"))
            rejected_values.append(entity.name)
            continue
        accepted.append(entity.model_copy(update={"name": candidate}))
        if candidate != normalize_text(entity.name):
            repaired.append(f"{field_key}: {entity.name} -> {candidate}")
    return accepted, EntityAuthenticityAudit(
        checked_count=len(values),
        accepted_count=len(accepted),
        rejected_count=len(values) - len(accepted),
        repaired_count=len(repaired),
        unsupported_count=unsupported_count,
        rejected_samples=tuple(_dedupe(rejected, limit=8)),
        repair_samples=tuple(_dedupe(repaired, limit=8)),
        rejected_values=tuple(_dedupe(rejected_values)),
    )


def _sanitize_graph(
    graph: ResearchEntityGraphOut,
    *,
    scope_hints: dict[str, object] | None,
) -> tuple[ResearchEntityGraphOut, EntityAuthenticityAudit]:
    known_names = _scope_known_names(scope_hints)
    accepted: list[ResearchNormalizedEntityOut] = []
    rejected: list[str] = []
    rejected_values: list[str] = []
    repaired: list[str] = []
    for entity in graph.entities:
        decision = evaluate_organization_name(
            entity.canonical_name,
            known_names=known_names,
            trusted_known_names=TRUSTED_ENTITY_NAMES,
        )
        if not decision.accepted or int(entity.source_count or 0) < 1:
            reason = decision.reason if not decision.accepted else "missing_source_support"
            rejected.append(_sample("entity_graph", entity.canonical_name, reason))
            rejected_values.append(entity.canonical_name)
            continue
        canonical = resolve_known_org_name(decision.normalized_name, scope_hints=scope_hints)
        aliases = [
            alias_decision.normalized_name
            for alias in [canonical, *entity.aliases]
            if (
                alias_decision := evaluate_organization_name(
                    alias,
                    known_names=known_names,
                    trusted_known_names=TRUSTED_ENTITY_NAMES,
                )
            ).accepted
        ]
        accepted.append(
            entity.model_copy(
                update={
                    "canonical_name": canonical,
                    "aliases": _dedupe(aliases, limit=8),
                }
            )
        )
        if canonical != normalize_text(entity.canonical_name):
            repaired.append(f"entity_graph: {entity.canonical_name} -> {canonical}")
    clean_graph = ResearchEntityGraphOut(
        entities=accepted,
        target_entities=[item for item in accepted if item.entity_type == "target"],
        competitor_entities=[item for item in accepted if item.entity_type == "competitor"],
        partner_entities=[item for item in accepted if item.entity_type == "partner"],
    )
    return clean_graph, EntityAuthenticityAudit(
        checked_count=len(graph.entities),
        accepted_count=len(accepted),
        rejected_count=len(graph.entities) - len(accepted),
        repaired_count=len(repaired),
        unsupported_count=sum(1 for sample in rejected if "missing_source_support" in sample),
        rejected_samples=tuple(_dedupe(rejected, limit=8)),
        repair_samples=tuple(_dedupe(repaired, limit=8)),
        rejected_values=tuple(_dedupe(rejected_values)),
    )


def enforce_report_entity_authenticity(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object] | None,
    prior_audit: dict[str, object] | None = None,
) -> ResearchReportResponse:
    updates: dict[str, object] = {}
    audits: list[EntityAuthenticityAudit] = [_audit_from_mapping(prior_audit)]
    for field_key in REPORT_ENTITY_FIELDS:
        cleaned, audit = _sanitize_entity_field_values(
            field_key,
            getattr(report, field_key, []),
            sources=source_documents,
            scope_hints=scope_hints,
            require_source_support=True,
        )
        updates[field_key] = cleaned
        audits.append(audit)
    for field_key in REPORT_ENTITY_CONTEXT_FIELDS:
        cleaned, audit = _sanitize_entity_context_values(
            field_key,
            getattr(report, field_key, []),
            sources=source_documents,
            scope_hints=scope_hints,
        )
        updates[field_key] = cleaned
        audits.append(audit)

    ranking_fields = (
        "top_target_accounts",
        "pending_target_candidates",
        "top_competitors",
        "pending_competitor_candidates",
        "top_ecosystem_partners",
        "pending_partner_candidates",
    )
    for field_key in ranking_fields:
        cleaned, audit = _sanitize_ranked_entities(
            field_key,
            getattr(report, field_key, []),
            sources=source_documents,
            scope_hints=scope_hints,
        )
        updates[field_key] = cleaned
        audits.append(audit)

    clean_graph, graph_audit = _sanitize_graph(report.entity_graph, scope_hints=scope_hints)
    updates["entity_graph"] = clean_graph
    audits.append(graph_audit)
    verified_targets = list(updates.get("target_accounts", []))
    verified_target_keys = {entity_canonical_key(value) for value in verified_targets}
    for entity in clean_graph.target_entities:
        candidate = normalize_text(entity.canonical_name)
        key = entity_canonical_key(candidate)
        if (
            not candidate
            or not key
            or key in verified_target_keys
            or not source_supports_local_target_role(
                candidate,
                sources=source_documents,
                scope_hints=scope_hints,
            )
        ):
            continue
        verified_targets.append(candidate)
        verified_target_keys.add(key)
    updates["target_accounts"] = verified_targets
    merged = _merge_audits(*audits)
    text_payload: dict[str, object] = {
        "report_title": report.report_title,
        "executive_summary": report.executive_summary,
        "consulting_angle": report.consulting_angle,
    }
    _scrub_rejected_entity_mentions(
        text_payload,
        rejected_values=merged.rejected_values,
        output_language=report.output_language,
    )
    updates.update(text_payload)

    gate = ResearchEntityAuthenticityGateOut(
        enforced=True,
        status="pass",
        passed=True,
        checked_count=merged.checked_count,
        accepted_count=merged.accepted_count,
        rejected_count=merged.rejected_count,
        repaired_count=merged.repaired_count,
        unsupported_count=merged.unsupported_count,
        rejected_samples=list(merged.rejected_samples),
        repair_samples=list(merged.repair_samples),
        warnings=(
            [f"生成过程中已剔除 {merged.rejected_count} 条非机构或无来源支撑的实体候选。"]
            if merged.rejected_count
            else []
        ),
    )
    diagnostics = report.source_diagnostics.model_copy(
        update={
            "entity_authenticity_gate_status": gate.status,
            "entity_authenticity_gate_passed": gate.passed,
            "entity_authenticity_checked_count": gate.checked_count,
            "entity_authenticity_rejected_count": gate.rejected_count,
            "entity_authenticity_repaired_count": gate.repaired_count,
            "entity_authenticity_unsupported_count": gate.unsupported_count,
            "entity_authenticity_rejected_samples": gate.rejected_samples,
            "entity_authenticity_repair_samples": gate.repair_samples,
        }
    )
    candidate = report.model_copy(
        update={
            **updates,
            "source_diagnostics": diagnostics,
            "research_entity_authenticity_gate": gate,
        }
    )

    remaining_invalid = [
        name
        for name in [
            *(value for field_key in REPORT_ENTITY_FIELDS for value in getattr(candidate, field_key, [])),
            *(entity.name for field_key in ranking_fields for entity in getattr(candidate, field_key, [])),
            *(entity.canonical_name for entity in candidate.entity_graph.entities),
        ]
        if not evaluate_organization_name(
            name,
            known_names=_scope_known_names(scope_hints),
            trusted_known_names=TRUSTED_ENTITY_NAMES,
        ).accepted
    ]
    if remaining_invalid:
        raise EntityAuthenticityGateError(
            f"Entity authenticity gate failed with {len(remaining_invalid)} invalid entities: {remaining_invalid[:3]}"
        )
    return candidate
