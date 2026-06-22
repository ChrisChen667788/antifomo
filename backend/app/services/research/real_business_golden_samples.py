from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.content_extractor import normalize_text


DATASET_PATH = Path(__file__).resolve().parents[3] / "evaluation" / "real_business_delivery_golden_v1.json"


@dataclass(frozen=True, slots=True)
class RealBusinessGoldenSource:
    title: str
    url: str
    domain: str
    snippet: str
    source_type: str
    source_tier: str
    search_query: str


@dataclass(frozen=True, slots=True)
class RealBusinessGoldenSample:
    sample_id: str
    topic: str
    scenario: str
    target_customer: str
    vertical_scene: str
    research_focus: str
    executive_summary: str
    consulting_angle: str
    target_accounts: tuple[str, ...]
    target_departments: tuple[str, ...]
    public_contact_channels: tuple[str, ...]
    budget_signals: tuple[str, ...]
    tender_timeline: tuple[str, ...]
    strategic_directions: tuple[str, ...]
    leadership_focus: tuple[str, ...]
    ecosystem_partners: tuple[str, ...]
    benchmark_cases: tuple[str, ...]
    flagship_products: tuple[str, ...]
    five_year_outlook: tuple[str, ...]
    competition_analysis: tuple[str, ...]
    query_plan: tuple[str, ...]
    sources: tuple[RealBusinessGoldenSource, ...]
    acceptance: dict[str, Any]


def _tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
    return tuple(rows)


def _source_from_dict(raw: dict[str, Any]) -> RealBusinessGoldenSource:
    return RealBusinessGoldenSource(
        title=normalize_text(raw.get("title")),
        url=normalize_text(raw.get("url")),
        domain=normalize_text(raw.get("domain")),
        snippet=normalize_text(raw.get("snippet")),
        source_type=normalize_text(raw.get("source_type")) or "policy",
        source_tier=normalize_text(raw.get("source_tier")) or "official",
        search_query=normalize_text(raw.get("search_query")),
    )


def _sample_from_dict(raw: dict[str, Any]) -> RealBusinessGoldenSample:
    sources = tuple(
        _source_from_dict(item)
        for item in raw.get("sources", [])
        if isinstance(item, dict) and normalize_text(item.get("url"))
    )
    return RealBusinessGoldenSample(
        sample_id=normalize_text(raw.get("sample_id")),
        topic=normalize_text(raw.get("topic")),
        scenario=normalize_text(raw.get("scenario")),
        target_customer=normalize_text(raw.get("target_customer")),
        vertical_scene=normalize_text(raw.get("vertical_scene")),
        research_focus=normalize_text(raw.get("research_focus")),
        executive_summary=normalize_text(raw.get("executive_summary")),
        consulting_angle=normalize_text(raw.get("consulting_angle")),
        target_accounts=_tuple(raw.get("target_accounts")),
        target_departments=_tuple(raw.get("target_departments")),
        public_contact_channels=_tuple(raw.get("public_contact_channels")),
        budget_signals=_tuple(raw.get("budget_signals")),
        tender_timeline=_tuple(raw.get("tender_timeline")),
        strategic_directions=_tuple(raw.get("strategic_directions")),
        leadership_focus=_tuple(raw.get("leadership_focus")),
        ecosystem_partners=_tuple(raw.get("ecosystem_partners")),
        benchmark_cases=_tuple(raw.get("benchmark_cases")),
        flagship_products=_tuple(raw.get("flagship_products")),
        five_year_outlook=_tuple(raw.get("five_year_outlook")),
        competition_analysis=_tuple(raw.get("competition_analysis")),
        query_plan=_tuple(raw.get("query_plan")),
        sources=sources,
        acceptance=raw.get("acceptance") if isinstance(raw.get("acceptance"), dict) else {},
    )


def load_real_business_delivery_golden_samples(
    path: Path = DATASET_PATH,
) -> tuple[RealBusinessGoldenSample, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else []
    if not isinstance(samples, list):
        return ()
    rows = [_sample_from_dict(item) for item in samples if isinstance(item, dict)]
    return tuple(sample for sample in rows if sample.sample_id and sample.topic and sample.sources)


def build_real_business_research_report(sample: RealBusinessGoldenSample) -> ResearchReportResponse:
    sources = [
        ResearchSourceOut(
            title=source.title,
            url=source.url,
            domain=source.domain,
            snippet=source.snippet,
            search_query=source.search_query,
            source_type=source.source_type,
            content_status="fetched",
            source_tier=source.source_tier,  # type: ignore[arg-type]
        )
        for source in sample.sources
    ]
    return ResearchReportResponse(
        keyword=sample.scenario,
        research_focus=sample.research_focus,
        output_language="zh-CN",
        research_mode="deep",
        report_title=sample.topic,
        executive_summary=sample.executive_summary,
        consulting_angle=sample.consulting_angle,
        target_accounts=list(sample.target_accounts),
        target_departments=list(sample.target_departments),
        public_contact_channels=list(sample.public_contact_channels),
        budget_signals=list(sample.budget_signals),
        tender_timeline=list(sample.tender_timeline),
        strategic_directions=list(sample.strategic_directions),
        leadership_focus=list(sample.leadership_focus),
        ecosystem_partners=list(sample.ecosystem_partners),
        benchmark_cases=list(sample.benchmark_cases),
        flagship_products=list(sample.flagship_products),
        five_year_outlook=list(sample.five_year_outlook),
        competition_analysis=list(sample.competition_analysis),
        source_count=len(sources),
        evidence_density="high",
        source_quality="high",
        query_plan=list(sample.query_plan),
        sources=sources,
        generated_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
