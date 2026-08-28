from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import re
from types import SimpleNamespace
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.archive_context import (
    merge_scope_hints_with_archive_context,
    render_archive_prompt_context,
    research_archive_query_text,
)
from app.services.research.archive_loader import (
    build_archive_context_item,
    build_archive_report_scope_hints,
    load_research_archive_context,
)
from app.services.research.followup_diagnostics import (
    FollowupDiagnosticsDependencies,
    build_followup_research_diagnostics,
)
from app.services.research.generation_artifacts import (
    build_partial_report_response,
    build_partial_report_result,
)
from app.services.research.generation_execution import (
    ResearchGenerationExecutionDependencies,
    execute_research_generation,
)
from app.services.research.report_row_quality import is_actionable_budget_row
from app.services.research.source_documents import SourceDocument
from app.services.research.source_query_plans import SourceQueryPlanDependencies, build_query_plan
from app.services.llm_parser import parse_research_report_response


def _new_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)


def _dedupe_strings(values: Iterable[object], limit: int) -> list[str]:
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


def _strip_query_noise(value: str) -> str:
    return normalize_text(value)


def _sanitize_research_focus_text(value: str | None) -> str:
    return normalize_text(value or "")


def _extract_topic_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    terms = [keyword]
    for token in ("政务云", "预算窗口", "南京市数据局", "上海数据集团"):
        if token in text:
            terms.append(token)
    return _dedupe_strings(terms, 8)


def _expand_region_scope_terms(regions: list[str]) -> list[str]:
    aliases = {"上海": ("上海市",), "江苏": ("南京",), "南京": ("江苏",)}
    expanded: list[str] = []
    for region in regions:
        normalized = normalize_text(region)
        if not normalized:
            continue
        expanded.append(normalized)
        expanded.extend(aliases.get(normalized, ()))
    return _dedupe_strings(expanded, 8)


def _source_query_plan_dependencies() -> SourceQueryPlanDependencies:
    return SourceQueryPlanDependencies(
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        expand_region_scope_terms=_expand_region_scope_terms,
        dedupe_strings=_dedupe_strings,
        collect_theme_seed_companies=lambda *args, **kwargs: [],
        is_plausible_entity_name=lambda value: bool(normalize_text(value)),
        industry_scope_aliases={"政务云": ("政务云", "政务", "数据局")},
        theme_query_expansion_templates={},
        research_source_site_queries=(),
        theme_official_query_templates={},
    )


def _merge_scope_hints(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, list):
            merged[key] = _dedupe_strings([*(merged.get(key, []) or []), *value], 8)
        elif value:
            merged[key] = value
    return merged


def _infer_input_scope_hints(keyword: str, research_focus: str | None) -> dict[str, object]:
    text = normalize_text(" ".join([keyword, research_focus or ""]))
    hints: dict[str, object] = {
        "regions": [],
        "industries": [],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": [],
    }
    if "上海" in text:
        hints["regions"] = ["上海"]
    if "南京" in text or "江苏" in text:
        hints["regions"] = _dedupe_strings([*(hints["regions"] or []), "江苏"], 4)
    if "政务云" in text or "电子政务" in text:
        hints["industries"] = ["政务云"]
    if "南京市数据局" in text:
        hints["clients"] = ["南京市数据局"]
        hints["company_anchors"] = ["南京市数据局"]
        hints["strategy_query_expansions"] = [
            '"南京市数据局" 政务云 采购意向 预算',
            '"南京市数据局" 电子政务云平台 招标 项目',
        ]
    if "上海数据集团" in text:
        hints["clients"] = _dedupe_strings([*(hints["clients"] or []), "上海数据集团"], 4)
        hints["company_anchors"] = _dedupe_strings([*(hints["company_anchors"] or []), "上海数据集团"], 4)
    return hints


def _build_theme_terms(keyword: str, research_focus: str | None, scope_hints: dict[str, object]) -> list[str]:
    return _dedupe_strings(
        [
            *_extract_topic_anchor_terms(keyword, research_focus),
            *list(scope_hints.get("industries", []) or []),
            *list(scope_hints.get("regions", []) or []),
        ],
        12,
    )


def _prune_industry_hints(values: list[str]) -> list[str]:
    return _dedupe_strings(values, 4)


def _truncate_text(value: str | None, limit: int) -> str:
    return normalize_text(value or "")[:limit]


def _report_sources_to_source_documents(sources: list[object]) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for source in sources:
        documents.append(
            SourceDocument(
                title=normalize_text(getattr(source, "title", "")),
                url=normalize_text(getattr(source, "url", "")),
                domain=normalize_text(getattr(source, "domain", "")),
                snippet=normalize_text(getattr(source, "snippet", "")),
                search_query=normalize_text(getattr(source, "search_query", "")),
                source_type=normalize_text(getattr(source, "source_type", "")) or "web",
                content_status=normalize_text(getattr(source, "content_status", "")) or "extracted",
                excerpt=normalize_text(getattr(source, "snippet", "")),
                source_label=normalize_text(getattr(source, "source_label", "")) or None,
                source_tier=getattr(source, "source_tier", "media"),
            )
        )
    return documents


def _build_archive_report_scope_hints(report: ResearchReportResponse) -> dict[str, object]:
    return build_archive_report_scope_hints(
        report,
        dedupe_strings=_dedupe_strings,
        prune_industry_hints=_prune_industry_hints,
        stored_report_concrete_targets=lambda stored_report: list(stored_report.target_accounts),
    )


def _resolve_stored_report_target_support(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
) -> tuple[list[str], list[str], list[str]]:
    targets = _dedupe_strings(report.target_accounts, 4)
    return targets, targets, []


def _build_archive_context_item(*, entry, match, scope_hints: dict[str, object]) -> dict[str, object] | None:
    return build_archive_context_item(
        entry=entry,
        match=match,
        scope_hints=scope_hints,
        truncate_text=_truncate_text,
        report_sources_to_source_documents=_report_sources_to_source_documents,
        merge_scope_hints=_merge_scope_hints,
        infer_input_scope_hints=_infer_input_scope_hints,
        build_archive_report_scope_hints=_build_archive_report_scope_hints,
        infer_scope_hints=lambda *args, **kwargs: {},
        assess_stored_report_rewrite_mode=lambda *args, **kwargs: ("rewrite", [], {}),
        resolve_stored_report_target_support=_resolve_stored_report_target_support,
        theme_labels_from_scope=lambda scope, **kwargs: list(scope.get("industries", []) or []),
        dedupe_strings=_dedupe_strings,
        sanitize_entity_row=lambda _field, value: normalize_text(value),
        is_trustworthy_scope_client_name=lambda *args, **kwargs: True,
        resolved_report_readiness=lambda report: SimpleNamespace(
            status="ready" if int(report.source_count or 0) >= 4 else "needs_evidence"
        ),
    )


def _research_archive_query_text(keyword: str, research_focus: str | None, scope_hints: dict[str, object]) -> str:
    return research_archive_query_text(keyword, research_focus, scope_hints, dedupe_strings=_dedupe_strings)


def _build_query_plan_for_followup(
    keyword: str,
    research_focus: str | None,
    include_wechat: bool,
    *,
    scope_hints: dict[str, object],
    limit: int,
) -> list[str]:
    return build_query_plan(
        keyword,
        research_focus,
        include_wechat,
        scope_hints=scope_hints,
        preferred_wechat_accounts=None,
        limit=limit,
        deps=_source_query_plan_dependencies(),
    )


def _followup_diagnostics_dependencies() -> FollowupDiagnosticsDependencies:
    return FollowupDiagnosticsDependencies(
        truncate_text=lambda value, limit: _truncate_text(value, limit),
        sanitize_research_focus_text=_sanitize_research_focus_text,
        looks_like_source_noise_segment=lambda *args, **kwargs: False,
        merge_scope_hints=_merge_scope_hints,
        dedupe_strings=_dedupe_strings,
        prune_industry_hints=_prune_industry_hints,
        infer_input_scope_hints=_infer_input_scope_hints,
        theme_labels_from_scope=lambda scope, **kwargs: list(scope.get("industries", []) or []),
        clean_scope_entity_names=lambda values, *, limit, **kwargs: _dedupe_strings(values, limit),
        build_query_plan=_build_query_plan_for_followup,
        extract_topic_anchor_terms=_extract_topic_anchor_terms,
        tokenize_for_match=lambda value, **kwargs: [token for token in re.split(r"\s+", normalize_text(value)) if token],
        generic_focus_tokens={"预算", "窗口", "采购"},
        org_pattern=re.compile(r"([\u4e00-\u9fa5]{2,40}(?:数据局|集团|公司|医院|中心))"),
    )


def _sanitize_report_field_rows(field_key: str, values: list[str]) -> list[str]:
    return _dedupe_strings(values, 4)


def _seed_demo_user(db: Session) -> User:
    settings = get_settings()
    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_stored_report(*, title: str, keyword: str) -> ResearchReportResponse:
    now = datetime.now(timezone.utc)
    return ResearchReportResponse(
        keyword=keyword,
        research_focus="梳理预算窗口、组织入口和推进策略",
        output_language="zh-CN",
        research_mode="deep",
        report_title=title,
        executive_summary="历史研报显示，上海数据集团 7 月前后将启动预算复核，采购中心和数字化部门是关键入口。",
        consulting_angle="适合作为预算窗口判断和打单路径设计的历史底稿。",
        target_accounts=["上海数据集团"],
        target_departments=["采购中心", "数字化部"],
        budget_signals=["7 月启动预算复核"],
        source_count=4,
        evidence_density="high",
        source_quality="high",
        sources=[
            {
                "title": "上海数据集团公开公告",
                "url": "https://example.com/shanghai-data",
                "domain": "example.com",
                "snippet": "预算复核与需求确认窗口",
                "search_query": keyword,
                "source_type": "policy",
                "content_status": "extracted",
                "source_label": "官网",
                "source_tier": "official",
            },
            {
                "title": "上海数据集团采购计划",
                "url": "https://example.com/shanghai-data-plan",
                "domain": "example.com",
                "snippet": "采购中心将同步梳理预算安排",
                "search_query": keyword,
                "source_type": "procurement",
                "content_status": "extracted",
                "source_label": "采购公告",
                "source_tier": "official",
            },
        ],
        source_diagnostics={
            "scope_regions": ["上海"],
            "scope_industries": ["政务云"],
            "scope_clients": ["上海数据集团"],
            "official_source_ratio": 0.75,
            "strict_match_ratio": 0.8,
            "retrieval_quality": "high",
            "evidence_mode": "strong",
        },
        generated_at=now,
    )


def test_load_research_archive_context_returns_supported_stored_reports() -> None:
    session_factory = _new_session_factory()

    with session_factory() as db:
        user = _seed_demo_user(db)
        report = _build_stored_report(title="上海数据集团预算窗口研判", keyword="上海数据集团预算窗口")
        entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title=report.report_title,
            content="聚焦预算复核、采购中心和数字化部的切入窗口。",
            source_domain="research.report",
            metadata_payload={"report": report.model_dump(mode="json")},
            is_focus_reference=True,
        )
        db.add(entry)
        db.commit()

    items = load_research_archive_context(
        keyword="上海数据集团预算窗口",
        research_focus="判断预算复核时间节点和组织入口",
        scope_hints={"industries": ["政务云"], "prefer_company_entities": True},
        limit=3,
        session_factory=session_factory,
        research_archive_query_text=_research_archive_query_text,
        build_archive_context_item=_build_archive_context_item,
    )

    assert items
    assert items[0]["kind"] == "stored_report"
    assert "上海数据集团" in items[0]["supported_targets"]
    assert items[0]["official_source_ratio"] >= 0.75
    assert "上海数据集团" in str(items[0]["match_snippet"])


def test_build_followup_research_diagnostics_rebuilds_filters_and_queries() -> None:
    followup_scope_hints, diagnostics = build_followup_research_diagnostics(
        keyword="政务云预算窗口",
        report_research_focus="梳理预算窗口和组织入口",
        followup_context=ResearchFollowupContextOut(
            supplemental_context="新增范围锁定到南京市数据局和电子政务云平台。",
            supplemental_evidence="公开线索提到 2026 年采购意向、预算安排和项目建设路径。",
            supplemental_requirements="优先补甲方、预算口径和采购意向公告。",
        ),
        include_wechat=False,
        base_scope_hints={"regions": [], "industries": ["政务云"], "clients": [], "company_anchors": []},
        deps=_followup_diagnostics_dependencies(),
    )

    assert diagnostics.enabled is True
    assert diagnostics.scope_rebuilt is True
    assert diagnostics.query_decomposition_applied is True
    assert "南京市数据局" in diagnostics.rebuilt_clients
    assert "政务云" in diagnostics.rebuilt_industries
    assert diagnostics.decomposition_queries
    assert any("南京市数据局" in query for query in diagnostics.decomposition_queries)
    assert followup_scope_hints.get("strategy_query_expansions")


def test_merge_scope_hints_with_archive_context_pushes_archive_targets_into_query_plan() -> None:
    base_scope_hints = {
        "regions": ["上海"],
        "industries": ["政务云"],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": [],
        "prefer_company_entities": False,
    }
    merged_scope_hints = merge_scope_hints_with_archive_context(
        base_scope_hints,
        [
            {
                "kind": "stored_report",
                "supported_targets": ["上海数据集团"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 4,
                "official_source_ratio": 0.75,
                "retrieval_quality": "high",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        keyword="上海政务云预算窗口",
        research_focus="优先锁定具体账户和采购中心",
        dedupe_strings=_dedupe_strings,
        sanitize_report_field_rows=_sanitize_report_field_rows,
        is_actionable_budget_row=is_actionable_budget_row,
        truncate_text=_truncate_text,
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
    )

    assert merged_scope_hints["archive_targets"] == ["上海数据集团"]
    assert "采购中心" in merged_scope_hints["archive_target_departments"]
    assert "7 月预算复核" in merged_scope_hints["archive_budget_signals"]
    queries = build_query_plan(
        "上海政务云预算窗口",
        "优先锁定具体账户和采购中心",
        False,
        scope_hints=merged_scope_hints,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any("上海数据集团" in query and "采购中心" in query for query in queries)
    assert any("上海数据集团" in query and "预算" in query for query in queries)


def test_merge_scope_hints_with_archive_context_does_not_pollute_industry_study_without_account_intent() -> None:
    base_scope_hints = {
        "regions": ["长三角"],
        "industries": ["文旅文博"],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": ["长三角 景区 博物馆 AI 招标 预算"],
        "prefer_company_entities": False,
    }

    merged_scope_hints = merge_scope_hints_with_archive_context(
        base_scope_hints,
        [
            {
                "kind": "stored_report",
                "supported_targets": ["国家消防救援局"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 5,
                "official_source_ratio": 0.8,
                "retrieval_quality": "high",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        keyword="2026年长三角文旅文博行业AI潜在需求及商机情报调研分析",
        research_focus=None,
        dedupe_strings=_dedupe_strings,
        sanitize_report_field_rows=_sanitize_report_field_rows,
        is_actionable_budget_row=is_actionable_budget_row,
        truncate_text=_truncate_text,
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
    )

    assert merged_scope_hints == base_scope_hints
    assert "国家消防救援局" not in str(merged_scope_hints)


def test_merge_scope_hints_with_archive_context_ignores_stale_low_support_archive_items() -> None:
    base_scope_hints = {
        "regions": ["上海"],
        "industries": ["政务云"],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": [],
        "prefer_company_entities": False,
    }
    merged_scope_hints = merge_scope_hints_with_archive_context(
        base_scope_hints,
        [
            {
                "kind": "stored_report",
                "supported_targets": ["上海数据集团"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 2,
                "official_source_ratio": 0.3,
                "retrieval_quality": "medium",
                "updated_at": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
        ],
        keyword="上海政务云预算窗口",
        research_focus="优先锁定具体账户和采购中心",
        dedupe_strings=_dedupe_strings,
        sanitize_report_field_rows=_sanitize_report_field_rows,
        is_actionable_budget_row=is_actionable_budget_row,
        truncate_text=_truncate_text,
        strip_query_noise=_strip_query_noise,
        sanitize_research_focus_text=_sanitize_research_focus_text,
    )

    assert "archive_targets" not in merged_scope_hints
    queries = build_query_plan(
        "上海政务云预算窗口",
        "优先锁定具体账户和采购中心",
        False,
        scope_hints=merged_scope_hints,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert not any("上海数据集团" in query and "采购中心" in query for query in queries)


class _CaptureLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        self.calls.append((prompt_name, dict(variables)))
        if prompt_name == "research_report_outline.txt":
            return (
                '{"report_title":"上海政务云推进研判","executive_summary":"先围绕上海数据集团做预算与组织入口判断。",'
                '"consulting_angle":"适合先做范围锁定和推进路径设计。"}'
            )
        if prompt_name == "research_report.txt":
            return """
            {
              "report_title": "上海政务云推进研判",
              "executive_summary": "先围绕上海数据集团做预算与组织入口判断，再补公开采购和官网证据。",
              "consulting_angle": "适合方案设计情报和打单推进双用途。",
              "industry_brief": [],
              "key_signals": [],
              "policy_and_leadership": [],
              "commercial_opportunities": [],
              "solution_design": [],
              "sales_strategy": [],
              "bidding_strategy": [],
              "outreach_strategy": [],
              "ecosystem_strategy": [],
              "target_accounts": ["上海数据集团"],
              "target_departments": ["采购中心"],
              "public_contact_channels": [],
              "account_team_signals": [],
              "budget_signals": ["7 月预算复核"],
              "project_distribution": [],
              "strategic_directions": [],
              "tender_timeline": [],
              "leadership_focus": [],
              "ecosystem_partners": [],
              "competitor_profiles": [],
              "benchmark_cases": [],
              "flagship_products": [],
              "key_people": [],
              "five_year_outlook": [],
              "client_peer_moves": [],
              "winner_peer_moves": [],
              "competition_analysis": [],
              "risks": [],
              "next_actions": []
            }
            """
        raise AssertionError(f"unexpected prompt: {prompt_name}")


class _FallbackCaptureLLM(_CaptureLLM):
    def __init__(self) -> None:
        super().__init__()
        self.last_run_result = None

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        if prompt_name == "research_report_outline.txt":
            raw = super().run_prompt(prompt_name, variables)
            self.last_run_result = SimpleNamespace(
                provider="openai",
                model="gpt-5.5",
                status="succeeded",
                metadata={"fallback_used": False},
            )
            return raw
        if prompt_name == "research_report.txt":
            self.calls.append((prompt_name, dict(variables)))
            self.last_run_result = SimpleNamespace(
                provider="mock",
                model="deterministic-mock",
                status="fallback",
                metadata={"fallback_used": True, "primary_error": "RuntimeError"},
            )
            return '{"report_title":"模板标题","executive_summary":"脏片段","consulting_angle":"模板角度"}'
        raise AssertionError(f"unexpected prompt: {prompt_name}")


def _build_partial_report_result_for_test(**kwargs):
    return build_partial_report_result(
        **kwargs,
        render_industry_methodology_context=lambda _scope_hints: "",
        apply_topic_specific_overrides=lambda parsed, **_kwargs: parsed,
    )


def _build_partial_report_response_for_test(**kwargs):
    return build_partial_report_response(
        **kwargs,
        evidence_density_level=lambda _sources, _parsed: "low",
        source_quality_level=lambda _sources: "low",
        build_sections=lambda _parsed, _output_language, _sources: [],
        source_documents_to_outputs=lambda _sources: [],
        enrich_report_for_delivery=lambda report: report,
    )


def test_execute_research_generation_passes_archive_context_into_outline_and_full_prompt() -> None:
    llm = _CaptureLLM()
    archive_context = render_archive_prompt_context(
        [
            {
                "kind": "stored_report",
                "title": "历史上海数据集团研判",
                "match_label": "补充新证据",
                "match_snippet": "上海数据集团将在 7 月启动预算复核。",
                "summary": "历史研报已锁定预算窗口和采购中心。",
                "supported_targets": ["上海数据集团"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 4,
                "official_source_ratio": 0.75,
                "score": 0.91,
            }
        ]
    )
    followup_context = ResearchFollowupContextOut(
        supplemental_context="新增范围集中到上海数据集团采购中心。",
        supplemental_evidence="新增证据显示 7 月预算复核后会同步确认采购安排。",
        supplemental_requirements="优先补采购中心、预算口径和官网公告。",
    )
    followup_diagnostics = ResearchFollowupDiagnosticsOut(
        enabled=True,
        scope_rebuilt=True,
        query_decomposition_applied=True,
        decomposition_queries=["上海数据集团 采购中心 预算复核"],
        rebuilt_clients=["上海数据集团"],
        rebuilt_industries=["政务云"],
    )

    execution = execute_research_generation(
        keyword="上海政务云预算窗口",
        research_focus="优先锁定具体账户和采购中心",
        report_research_focus="优先锁定具体账户和采购中心",
        output_language="zh-CN",
        research_mode="fast",
        archive_context=archive_context,
        followup_context=followup_context,
        followup_diagnostics=followup_diagnostics,
        source_intelligence={"target_accounts": ["上海数据集团"]},
        scope_hints={"regions": ["上海"], "industries": ["政务云"], "clients": ["上海数据集团"]},
        llm=llm,
        runtime={"llm_timeout_seconds": 30},
        effective_query_plan=["上海政务云预算窗口"],
        adapter_query_plan=[],
        sources=[],
        source_diagnostics=ResearchSourceDiagnosticsOut(),
        entity_graph=ResearchEntityGraphOut(),
        retrieval_correction_profile=SimpleNamespace(),
        progress_callback=None,
        snapshot_callback=None,
        section_retrieval_dependencies={},
        deps=ResearchGenerationExecutionDependencies(
            build_partial_report_result=_build_partial_report_result_for_test,
            render_followup_diagnostics_prompt_context=lambda diagnostics: (
                f"二次检索摘要：{'；'.join(diagnostics.decomposition_queries)}；采购中心"
            ),
            emit_research_progress=lambda *args, **kwargs: None,
            build_progress_message=lambda value, **kwargs: value,
            build_partial_report_response=_build_partial_report_response_for_test,
            build_section_retrieval_runtime_context=lambda **kwargs: SimpleNamespace(
                followup_section_focus_context="采购中心",
                section_retrieval_context="",
            ),
            emit_research_snapshot=lambda *args, **kwargs: None,
            render_source_digest=lambda _sources: "",
            render_followup_prompt_context=lambda context: context.supplemental_context,
            render_retrieval_correction_context=lambda _profile: "",
            render_industry_methodology_context=lambda _scope_hints: "",
            parse_research_report_response=parse_research_report_response,
            merge_result_with_intelligence=lambda parsed, _intelligence, **_kwargs: parsed,
            apply_topic_specific_overrides=lambda parsed, **_kwargs: parsed,
            apply_strategy_llm_refinement=lambda parsed, **_kwargs: parsed,
        ),
    )

    assert "上海" in execution.parsed.report_title
    outline_call = next(call for call in llm.calls if call[0] == "research_report_outline.txt")
    full_call = next(call for call in llm.calls if call[0] == "research_report.txt")
    assert outline_call[1]["__timeout_seconds"] == "30"
    assert "上海数据集团" in outline_call[1]["archive_context"]
    assert "预算复核" in outline_call[1]["archive_context"]
    assert "上海数据集团" in full_call[1]["archive_context"]
    assert "预算复核" in full_call[1]["archive_context"]
    assert "二次检索摘要" in outline_call[1]["followup_diagnostics"]
    assert "采购中心" in full_call[1]["followup_diagnostics"]


def test_execute_research_generation_marks_fallback_and_preserves_remote_outline() -> None:
    llm = _FallbackCaptureLLM()

    execution = execute_research_generation(
        keyword="长三角文旅文博人工智能",
        research_focus="研判景区和博物馆的人工智能机会",
        report_research_focus="研判景区和博物馆的人工智能机会",
        output_language="zh-CN",
        research_mode="deep",
        archive_context="",
        followup_context=ResearchFollowupContextOut(),
        followup_diagnostics=ResearchFollowupDiagnosticsOut(),
        source_intelligence={"risks": [], "next_actions": []},
        scope_hints={"regions": ["长三角"], "industries": ["文旅文博"]},
        llm=llm,
        runtime={"llm_timeout_seconds": 30},
        effective_query_plan=["长三角 文旅文博 人工智能"],
        adapter_query_plan=[],
        sources=[],
        source_diagnostics=ResearchSourceDiagnosticsOut(),
        entity_graph=ResearchEntityGraphOut(),
        retrieval_correction_profile=SimpleNamespace(),
        progress_callback=None,
        snapshot_callback=None,
        section_retrieval_dependencies={},
        deps=ResearchGenerationExecutionDependencies(
            build_partial_report_result=_build_partial_report_result_for_test,
            render_followup_diagnostics_prompt_context=lambda _diagnostics: "",
            emit_research_progress=lambda *args, **kwargs: None,
            build_progress_message=lambda value, **kwargs: value,
            build_partial_report_response=_build_partial_report_response_for_test,
            build_section_retrieval_runtime_context=lambda **kwargs: SimpleNamespace(
                followup_section_focus_context="",
                section_retrieval_context="",
            ),
            emit_research_snapshot=lambda *args, **kwargs: None,
            render_source_digest=lambda _sources: "",
            render_followup_prompt_context=lambda _context: "",
            render_retrieval_correction_context=lambda _profile: "",
            render_industry_methodology_context=lambda _scope_hints: "",
            parse_research_report_response=parse_research_report_response,
            merge_result_with_intelligence=lambda parsed, _intelligence, **_kwargs: parsed,
            apply_topic_specific_overrides=lambda parsed, **_kwargs: parsed,
            apply_strategy_llm_refinement=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("fallback drafts must not be strategy-refined")
            ),
        ),
    )

    assert execution.generation_fallback_used is True
    assert execution.generation_provider == "mock"
    assert execution.generation_model == "deterministic-mock"
    assert execution.parsed.report_title == "上海政务云推进研判"
    assert "上海数据集团" in execution.parsed.executive_summary
    assert "降级草稿" in execution.parsed.risks[-1]
    assert "重新生成正式研报" in execution.parsed.next_actions[-1]
