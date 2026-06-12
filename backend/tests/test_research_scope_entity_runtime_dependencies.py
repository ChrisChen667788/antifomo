from __future__ import annotations

from pathlib import Path

from app.services import research_service
from app.services.research.report_runtime_dependencies import (
    action_card_dependencies,
    report_readiness_dependencies,
    stored_report_rewrite_dependencies,
    stored_report_rewrite_orchestration_dependencies,
)
from app.services.research.report_runtime_owner_factory import build_report_runtime_owner_ports
from app.services.research.report_ranking_runtime import build_runtime_source_diagnostics
from app.services.research.report_delivery_runtime import (
    evidence_density_level,
    merge_result_with_intelligence,
    source_quality_level,
)
from app.services.research.report_delivery_runtime_dependencies import (
    build_sections,
    enrich_report_for_delivery,
)
from app.services.research.report_delivery_strategy_runtime import (
    apply_topic_specific_overrides,
    compress_title_segments,
    summary_contains_output_noise,
)
from app.services.research.report_scope_runtime import (
    collect_matched_theme_labels,
    prune_industry_hints,
    scope_anchor_text_segments,
)
from app.services.research.report_storage_runtime import (
    report_intelligence_from_result,
    report_sources_to_documents,
    stored_report_to_runtime_result,
)
from app.services.research.stored_entity_runtime_dependencies import (
    canonicalize_entity_name,
    canonicalize_report_entities,
    canonicalize_result_entities,
    clean_candidate_company_names,
)
from app.services.research.scope_hints import (
    infer_input_scope_hints,
    infer_scope_hints,
    merge_scope_hints,
    source_theme_match_score,
)
from app.services.research.entity_ranking import rank_report_entities
from app.services.research.entity_ranking_runtime import (
    build_entity_specific_contact_rows,
    build_entity_specific_team_rows,
    build_runtime_entity_graph,
    filtered_rank_fallback_values,
    rank_runtime_top_entities,
    source_supports_target_account,
)
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.source_intelligence_runtime import build_source_intelligence


def test_scope_entity_runtime_functions_preserve_facade_behavior() -> None:
    runtime = scope_entity_runtime_functions()
    scope_hints = {
        "regions": ["上海"],
        "industries": ["政务云"],
        "clients": ["上海数据集团"],
    }

    assert runtime.build_theme_terms(
        "上海政务云预算窗口",
        "锁定数据局和采购计划",
        scope_hints,
    ) == research_service._build_theme_terms(
        "上海政务云预算窗口",
        "锁定数据局和采购计划",
        scope_hints,
    )
    assert runtime.theme_labels_from_scope(
        scope_hints,
        keyword="上海政务云预算窗口",
        research_focus="锁定数据局和采购计划",
    ) == research_service._theme_labels_from_scope(
        scope_hints,
        keyword="上海政务云预算窗口",
        research_focus="锁定数据局和采购计划",
    )

    for field_key, row in (
        ("target_accounts", "上海数据集团：采购预算与招标计划"),
        ("competitor_profiles", "华为云：中标政务云平台项目"),
        ("ecosystem_partners", "德勤：联合咨询与交付伙伴"),
        ("target_accounts", "当前证据不足，建议补充具体公司"),
    ):
        assert runtime.sanitize_entity_row(field_key, row) == research_service._sanitize_entity_row(field_key, row)


def test_report_runtime_dependencies_use_scope_entity_factory_functions() -> None:
    scope_hints = {"industries": ["AI漫剧"], "clients": ["爱奇艺"]}
    expected_terms = research_service._build_theme_terms("AI漫剧头部公司", "分析平台商业化路径", scope_hints)
    expected_labels = research_service._theme_labels_from_scope(
        scope_hints,
        keyword="AI漫剧头部公司",
        research_focus="分析平台商业化路径",
    )

    owners = build_report_runtime_owner_ports()
    action_deps = action_card_dependencies(owners)
    readiness_deps = report_readiness_dependencies(owners)
    rewrite_deps = stored_report_rewrite_dependencies(owners)
    orchestration_deps = stored_report_rewrite_orchestration_dependencies(owners)

    assert action_deps.theme_labels_from_scope(
        scope_hints,
        keyword="AI漫剧头部公司",
        research_focus="分析平台商业化路径",
    ) == expected_labels
    assert rewrite_deps.build_theme_terms("AI漫剧头部公司", "分析平台商业化路径", scope_hints) == expected_terms
    assert orchestration_deps.build_theme_terms(
        "AI漫剧头部公司",
        "分析平台商业化路径",
        scope_hints,
    ) == expected_terms

    row = "爱奇艺：推进 AI 漫剧平台采购与商业化"
    assert readiness_deps.sanitize_entity_row("target_accounts", row) == research_service._sanitize_entity_row(
        "target_accounts",
        row,
    )
    assert orchestration_deps.sanitize_report_field_rows("target_accounts", [row]) == research_service._sanitize_report_field_rows(
        "target_accounts",
        [row],
    )


def test_report_runtime_owner_ports_are_grouped_and_use_migrated_owners() -> None:
    owners = build_report_runtime_owner_ports()

    assert owners.scope.source_theme_match_score is source_theme_match_score
    assert owners.scope.infer_input_scope_hints is infer_input_scope_hints
    assert owners.scope.merge_scope_hints is merge_scope_hints
    assert owners.scope.infer_scope_hints is infer_scope_hints
    assert owners.scope.prune_industry_hints is prune_industry_hints
    assert owners.scope.collect_matched_theme_labels is collect_matched_theme_labels
    assert owners.scope.scope_anchor_text_segments is scope_anchor_text_segments
    assert owners.storage.report_sources_to_source_documents is report_sources_to_documents
    assert owners.storage.canonicalize_stored_report_entities is canonicalize_report_entities
    assert owners.storage.canonicalize_stored_entity_name is canonicalize_entity_name
    assert owners.storage.clean_candidate_profile_company_names is clean_candidate_company_names
    assert owners.storage.stored_report_to_result is stored_report_to_runtime_result
    assert owners.storage.report_intelligence_from_result is report_intelligence_from_result
    assert owners.storage.canonicalize_stored_result_entities is canonicalize_result_entities
    assert owners.ranking.rank_report_entities is rank_report_entities
    assert owners.ranking.source_supports_target_account is source_supports_target_account
    assert owners.ranking.build_entity_graph is build_runtime_entity_graph
    assert owners.ranking.build_source_diagnostics is build_runtime_source_diagnostics
    assert owners.ranking.rank_top_entities is rank_runtime_top_entities
    assert owners.ranking.filtered_rank_fallback_values is filtered_rank_fallback_values
    assert owners.ranking.build_entity_specific_contact_rows is build_entity_specific_contact_rows
    assert owners.ranking.build_entity_specific_team_rows is build_entity_specific_team_rows
    assert owners.delivery.source_quality_level is source_quality_level
    assert owners.delivery.evidence_density_level is evidence_density_level
    assert owners.delivery.merge_result_with_intelligence is merge_result_with_intelligence
    assert owners.delivery.compress_title_segments is compress_title_segments
    assert owners.delivery.summary_contains_output_noise is summary_contains_output_noise
    assert owners.delivery.build_source_intelligence is build_source_intelligence
    assert owners.delivery.apply_topic_specific_overrides is apply_topic_specific_overrides
    assert owners.delivery.build_sections is build_sections
    assert owners.delivery.enrich_report_for_delivery is enrich_report_for_delivery


def test_report_runtime_dependency_modules_do_not_reach_back_into_facade() -> None:
    services_dir = Path(__file__).resolve().parents[1] / "app" / "services" / "research"
    facade_source = (services_dir.parent / "research_service.py").read_text(encoding="utf-8")
    entity_policy_source = (services_dir / "entity_policy.py").read_text(encoding="utf-8")
    report_runtime_source = (services_dir / "report_runtime_dependencies.py").read_text(encoding="utf-8")
    report_owner_factory_source = (services_dir / "report_runtime_owner_factory.py").read_text(encoding="utf-8")
    scope_entity_source = (services_dir / "scope_entity_runtime_dependencies.py").read_text(encoding="utf-8")
    facade_reference_modules = {
        path.name
        for path in services_dir.glob("*.py")
        if "research_service" in path.read_text(encoding="utf-8")
    }

    assert not hasattr(research_service, "build_report_runtime_owner_ports")
    assert "build_scope_entity_owner_ports" not in facade_source
    assert "def build_report_runtime_owner_ports" not in facade_source
    assert "research_service" not in entity_policy_source
    assert "research_service" not in report_runtime_source
    assert "research_runtime" not in report_runtime_source
    assert "from app.services import" not in report_runtime_source
    assert "research_service" not in report_owner_factory_source
    for migrated_name in (
        "_prune_industry_hints",
        "_collect_matched_theme_labels",
        "_scope_anchor_text_segments",
        "_source_theme_match_score",
        "_infer_input_scope_hints",
        "_merge_scope_hints",
        "_infer_scope_hints",
        "_report_sources_to_source_documents",
        "_stored_report_to_result",
        "_report_intelligence_from_result",
        "_canonicalize_stored_report_entities",
        "_canonicalize_stored_entity_name",
        "_clean_candidate_profile_company_names",
        "_canonicalize_stored_result_entities",
        "_entity_ranking_rank_report_entities",
        "_source_quality_level",
        "_evidence_density_level",
        "_merge_result_with_intelligence",
        "_resolve_stored_report_target_support",
        "_apply_guarded_rewrite_diagnostics",
        "_assess_stored_report_rewrite_mode",
        "_build_guarded_rewrite_title",
        "_build_source_diagnostics",
        "_source_supports_target_account",
        "_build_entity_graph",
        "_rank_top_entities",
        "_filtered_rank_fallback_values",
        "_build_entity_specific_contact_rows",
        "_build_entity_specific_team_rows",
        "_compress_title_segments",
        "_summary_contains_output_noise",
        "_build_source_intelligence",
        "_apply_topic_specific_overrides",
        "_build_sections",
        "_enrich_report_for_delivery",
    ):
        assert f"facade.{migrated_name}" not in report_owner_factory_source
    assert "facade.SOURCE_MAX_AGE_YEARS" not in report_owner_factory_source
    assert facade_reference_modules == set()
    assert "sys.modules" not in scope_entity_source
    assert "runtime._" not in scope_entity_source
