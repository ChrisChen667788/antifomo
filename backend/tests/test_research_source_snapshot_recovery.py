from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import app.services.research.source_snapshot_recovery as snapshot_recovery
from app.services.research.source_snapshot_recovery import (
    EVIDENCE_SNAPSHOT_CANDIDATE_STATUSES,
    build_recent_evidence_snapshot,
    load_recent_evidence_snapshot,
)
from app.services.research.generation_workflow import (
    _accumulate_snapshot_source_pool,
    _build_snapshot_recovery_scope_hints,
)
from app.services.research.report_storage_runtime import dedupe_sources
from app.services.research.source_documents import SourceDocument


KEYWORD = "长三角文旅文博人工智能"
FOCUS = "研判景区、博物馆与公共文化场景的人工智能机会"


def _report_payload() -> dict[str, object]:
    domains = [
        "www.mct.gov.cn",
        "whhlyt.zj.gov.cn",
        "www.ccgp.gov.cn",
        "museum.example.cn",
        "tourism.example.cn",
        "culture.example.cn",
        "travel.example.cn",
        "ai.example.cn",
    ]
    return {
        "research_evidence_gate": {
            "passed": True,
            "formal_report_allowed": True,
            "accepted_source_count": 8,
            "official_source_count": 3,
            "unique_domain_count": 8,
        },
        "sources": [
            {
                "title": f"文旅人工智能来源 {index}",
                "url": f"https://{domain}/article/{index}",
                "domain": domain,
                "snippet": "文旅、景区、博物馆、公共文化、采购、方案、投入、交付和数据安全证据。",
                "search_query": "长三角 文旅 人工智能",
                "source_type": "policy" if index < 3 else "web",
                "content_status": "extracted",
                "source_label": domain,
                "source_tier": "official" if index < 3 else "media",
            }
            for index, domain in enumerate(domains)
        ],
    }


def test_build_recent_snapshot_requires_exact_topic_and_preserves_gate_quality() -> None:
    now = datetime(2026, 7, 15, 8, tzinfo=timezone.utc)

    snapshot = build_recent_evidence_snapshot(
        job_id="passed-job",
        job_keyword=KEYWORD,
        job_research_focus=FOCUS,
        finished_at=now - timedelta(hours=3, minutes=20),
        report_payload=_report_payload(),
        keyword=KEYWORD,
        research_focus=FOCUS,
        max_age_hours=48,
        now=now,
    )

    assert snapshot is not None
    assert snapshot.job_id == "passed-job"
    assert snapshot.age_hours == 3
    assert len(snapshot.sources) == 8
    assert sum(source.source_tier == "official" for source in snapshot.sources) == 3
    assert all(source.source_origin == "snapshot_cache" for source in snapshot.sources)


def test_snapshot_candidates_include_evidence_passed_delivery_failures() -> None:
    assert EVIDENCE_SNAPSHOT_CANDIDATE_STATUSES == ("succeeded", "needs_evidence")


def test_snapshot_loader_skips_rejected_newer_jobs(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    jobs = [
        SimpleNamespace(
            id="newer-job",
            keyword=KEYWORD,
            research_focus=FOCUS,
            finished_at=now - timedelta(minutes=5),
            report_payload=_report_payload(),
        ),
        SimpleNamespace(
            id="older-valid-job",
            keyword=KEYWORD,
            research_focus=FOCUS,
            finished_at=now - timedelta(minutes=10),
            report_payload=_report_payload(),
        ),
    ]

    class _Rows:
        def all(self):
            return jobs

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def scalars(self, _statement):
            return _Rows()

    monkeypatch.setattr(snapshot_recovery, "SessionLocal", _Session)

    snapshot = load_recent_evidence_snapshot(
        keyword=KEYWORD,
        research_focus=FOCUS,
        max_age_hours=48,
        excluded_job_ids=("newer-job",),
    )

    assert snapshot is not None
    assert snapshot.job_id == "older-valid-job"


def test_build_recent_snapshot_rejects_stale_mismatched_or_unpassed_reports() -> None:
    now = datetime(2026, 7, 15, 8, tzinfo=timezone.utc)
    common = {
        "job_id": "prior-job",
        "job_keyword": KEYWORD,
        "job_research_focus": FOCUS,
        "finished_at": now - timedelta(hours=2),
        "report_payload": _report_payload(),
        "keyword": KEYWORD,
        "research_focus": FOCUS,
        "max_age_hours": 48,
        "now": now,
    }

    assert build_recent_evidence_snapshot(**{**common, "research_focus": "不同研究范围"}) is None
    assert build_recent_evidence_snapshot(
        **{**common, "finished_at": now - timedelta(hours=49)}
    ) is None
    failed_payload = _report_payload()
    failed_payload["research_evidence_gate"] = {
        "passed": False,
        "formal_report_allowed": False,
        "accepted_source_count": 8,
        "official_source_count": 3,
        "unique_domain_count": 8,
    }
    assert build_recent_evidence_snapshot(**{**common, "report_payload": failed_payload}) is None


def test_snapshot_recovery_scope_does_not_inherit_company_seeds_from_noisy_fresh_results() -> None:
    recovered = _build_snapshot_recovery_scope_hints(
        input_scope_hints={
            "input_scope_locked": True,
            "regions": ["长三角"],
            "industries": ["文旅文博"],
            "clients": [],
            "company_anchors": [],
            "seed_companies": [],
            "prefer_company_entities": False,
            "prefer_head_companies": False,
        },
        current_scope_hints={
            "company_anchors": ["阿里云", "腾讯云"],
            "seed_companies": ["阿里云", "腾讯云"],
            "runtime_strategy_status": "ready",
        },
        inferred_scope_hints={
            "company_anchors": ["阿里云", "腾讯云"],
            "seed_companies": ["阿里云", "腾讯云"],
        },
        merge_scope_hints=lambda base, refined: {**base, **refined},
    )

    assert recovered["company_anchors"] == []
    assert recovered["seed_companies"] == []
    assert recovered["prefer_company_entities"] is False
    assert recovered["runtime_strategy_status"] == "ready"


def test_snapshot_recovery_accumulates_complementary_sources_across_jobs() -> None:
    def source(index: int) -> SourceDocument:
        return SourceDocument(
            title=f"政务人工智能来源 {index}",
            url=f"https://gov.example/{index}",
            domain="gov.example",
            snippet="政务人工智能采购与建设证据。",
            search_query="政务人工智能",
            source_type="policy",
            content_status="extracted",
            excerpt="政务人工智能采购与建设证据。",
            source_label="政府网站",
            source_tier="official",
            source_origin="snapshot_cache",
        )

    first = _accumulate_snapshot_source_pool([], [source(1), source(2)], dedupe_sources=dedupe_sources)
    combined = _accumulate_snapshot_source_pool(
        first,
        [source(2), source(3)],
        dedupe_sources=dedupe_sources,
    )

    assert [item.url for item in combined] == [
        "https://gov.example/1",
        "https://gov.example/2",
        "https://gov.example/3",
    ]
