from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Mapping


REGISTRY_VERSION = "2026.08.12-p5-full-content-industry-rag"


_INTERNAL_SKILL_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "skill_id": "delivery.architecture_exports",
        "name": "解决方案架构导出包",
        "version": "2026.06.30",
        "stage": "production",
        "evaluation_status": "passed",
        "owner": "research-delivery",
        "license": "internal",
        "data_boundary": "local_only",
        "external_api_status": "none",
        "secret_status": "not_required",
        "default_enabled": True,
        "dependencies": [
            {
                "name": "app.services.delivery.solution_architecture",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
            {
                "name": "app.services.delivery.solution_materials",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
        ],
        "regression_suites": [
            {
                "path": "backend/tests/test_research_solution_intelligence_service.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_delivery_solution_materials.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_research_solution_delivery_exports.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
        ],
        "applicable_documents": [
            "docs/professional-report-quality-v1.8.0.md",
            "solution-delivery-pack",
            "technical-workshop-pack",
        ],
        "baselines": [
            "architecture_export_bundle is present in solution delivery packs",
            "ADR table, dependency workshop, stakeholder brief and agenda are generated locally",
        ],
        "version_history": [
            {
                "version": "2026.06.30",
                "released_at": "2026-06-30",
                "change_summary": "Promoted architecture export bundle to the default solution delivery chain.",
                "rollback": "Remove architecture_export_bundle assembly from research_solution_intelligence_service.",
            },
        ],
        "rollback": "Disable the architecture export bundle injection point and keep solution materials generation local.",
        "notes": "No external API or data egress is required.",
    },
    {
        "skill_id": "knowledge.industry_reference_library",
        "name": "本地行业资料技能库",
        "version": "2026.08.12-rag",
        "stage": "production",
        "evaluation_status": "passed",
        "owner": "research-delivery",
        "license": "user_provided_local_reference",
        "data_boundary": "local_app",
        "external_api_status": "none",
        "secret_status": "not_required",
        "default_enabled": True,
        "dependencies": [
            {
                "name": "app.services.industry_skill_library",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
            {
                "name": "pdftotext",
                "dependency_type": "local_cli",
                "optional": True,
                "license": "system_package",
            },
            {
                "name": "SQLite FTS5 / local sentence-transformers embedding",
                "dependency_type": "local_runtime",
                "optional": False,
                "license": "system_and_model_cache",
            },
        ],
        "regression_suites": [
            {
                "path": "backend/tests/test_industry_skill_library.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_research_solution_intelligence_service.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_industry_knowledge_rag.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
        ],
        "applicable_documents": [
            "solution-delivery-pack",
            "feasibility-study",
            "project-proposal",
            "client-ppt-outline",
        ],
        "baselines": [
            "local source files are never moved or uploaded by the skill builder",
            "industry references do not increase project evidence counts or source support scores",
            "selected skills expose file-level references and a local-only data boundary",
            "full-content profiles retain coverage and OCR state; hybrid retrieval never treats local text as project evidence",
        ],
        "version_history": [
            {
                "version": "2026.08.12-rag",
                "released_at": "2026-08-12",
                "change_summary": "Promoted full-content parsing, macOS Vision OCR, SQLite FTS5 and local vector hybrid retrieval into the solution-intelligence path.",
                "rollback": "Set use_industry_skills=false or remove the generated local catalog and RAG artifacts; project evidence gates remain unchanged.",
            },
        ],
        "rollback": "Disable industry skill selection in solution delivery and remove the generated .tmp/industry-skills catalog; no source originals are changed.",
        "notes": "Uses only user-provided local files. Full text, OCR and vectors remain local; retrieved passages are untrusted references and never project evidence substitutes.",
    },
    {
        "skill_id": "delivery.formal_document_export",
        "name": "正式文档本地导出",
        "version": "2026.06.28",
        "stage": "production",
        "evaluation_status": "passed",
        "owner": "formal-delivery",
        "license": "internal",
        "data_boundary": "local_app",
        "external_api_status": "none",
        "secret_status": "not_required",
        "default_enabled": True,
        "dependencies": [
            {
                "name": "app.services.work_tasks.formal_documents",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
            {
                "name": "local Office / Preview GUI",
                "dependency_type": "local_application",
                "optional": True,
                "license": "user_environment",
            },
        ],
        "regression_suites": [
            {
                "path": "backend/tests/test_formal_document_rendering.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_delivery_document_compilers.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_delivery_golden_samples.py",
                "gate": "pytest",
                "cadence": "release-candidate",
            },
        ],
        "applicable_documents": [
            "docs/professional-report-quality-v1.8.0.md",
            "feasibility-report",
            "bidding-proposal",
            "solution-plan",
        ],
        "baselines": [
            "DOCX/PDF section numbering and evidence anchors survive local render checks",
            "PPTX overflow and media manifest checks are deterministic",
        ],
        "version_history": [
            {
                "version": "2026.06.28",
                "released_at": "2026-06-28",
                "change_summary": "Stabilized local formal document rendering and GUI gate metadata.",
                "rollback": "Fallback to markdown and HTML export artifacts while keeping source sections intact.",
            },
        ],
        "rollback": "Disable formal DOCX/PDF/PPTX export actions and retain markdown delivery output.",
        "notes": "Uses local applications only when the user invokes visual verification.",
    },
    {
        "skill_id": "research.evidence_grounding",
        "name": "研究报告证据约束生成",
        "version": "2026.06.29",
        "stage": "production",
        "evaluation_status": "passed",
        "owner": "research-quality",
        "license": "internal",
        "data_boundary": "local_only",
        "external_api_status": "none",
        "secret_status": "not_required",
        "default_enabled": True,
        "dependencies": [
            {
                "name": "app.services.research.report_delivery_runtime",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
            {
                "name": "app.services.research.source_intelligence_runtime",
                "dependency_type": "internal_module",
                "optional": False,
                "license": "internal",
            },
        ],
        "regression_suites": [
            {
                "path": "backend/tests/test_research_section_evidence.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_research_delivery_semantic_quality.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
            {
                "path": "backend/tests/test_research_archive_context.py",
                "gate": "pytest",
                "cadence": "per-change",
            },
        ],
        "applicable_documents": [
            "research-report",
            "delivery-solution-pack",
            "markdown-archive",
        ],
        "baselines": [
            "High-confidence claims require evidence anchors",
            "Low-quality report rewrite keeps source diagnostics visible",
        ],
        "version_history": [
            {
                "version": "2026.06.29",
                "released_at": "2026-06-29",
                "change_summary": "Kept evidence-aware generation in the default research delivery chain.",
                "rollback": "Route report generation to stored markdown without delivery pack promotion.",
            },
        ],
        "rollback": "Disable evidence pack promotion and keep source report payloads unchanged.",
        "notes": "Local deterministic checks only; provider calls remain governed by the LLM configuration panel.",
    },
    {
        "skill_id": "third_party.skillhub.word_docx",
        "name": "SkillHub Word DOCX 测试包",
        "version": "unreviewed",
        "stage": "third_party_test_package",
        "evaluation_status": "not_evaluated",
        "owner": "external-review",
        "license": "third_party_unknown",
        "data_boundary": "external_blocked",
        "external_api_status": "blocked_until_review",
        "secret_status": "blocked_until_review",
        "default_enabled": False,
        "dependencies": [
            {
                "name": "github.com/iflytek/skillhub",
                "dependency_type": "third_party_repository",
                "optional": True,
                "license": "unknown",
            },
        ],
        "regression_suites": [],
        "applicable_documents": ["docx-export"],
        "baselines": [],
        "version_history": [],
        "rollback": "Remove the converted test package from local experiments.",
        "notes": "Registered for review only; not admitted to production generation.",
    },
    {
        "skill_id": "third_party.skillhub.proofreading",
        "name": "第三方校对测试包",
        "version": "unreviewed",
        "stage": "third_party_test_package",
        "evaluation_status": "not_evaluated",
        "owner": "external-review",
        "license": "third_party_unknown",
        "data_boundary": "external_blocked",
        "external_api_status": "blocked_until_review",
        "secret_status": "required_for_optional_external_api",
        "default_enabled": False,
        "dependencies": [
            {
                "name": "external proofreading API",
                "dependency_type": "external_service",
                "optional": True,
                "license": "unknown",
            },
        ],
        "regression_suites": [],
        "applicable_documents": ["formal-document-proofreading"],
        "baselines": [],
        "version_history": [],
        "rollback": "Keep local deterministic proofreading and reject external upload attempts.",
        "notes": "External upload remains blocked until data boundary and license review pass.",
    },
)


def _is_allowed_in_default_generation_chain(entry: Mapping[str, Any]) -> bool:
    return (
        bool(entry.get("default_enabled"))
        and entry.get("stage") == "production"
        and entry.get("evaluation_status") == "passed"
        and entry.get("external_api_status") in {"none", "optional_disabled"}
        and entry.get("data_boundary") in {"local_only", "local_app"}
        and entry.get("secret_status") == "not_required"
    )


def _admission_reason(entry: Mapping[str, Any]) -> str:
    if _is_allowed_in_default_generation_chain(entry):
        return "passed production skill with local data boundary"
    if entry.get("stage") != "production":
        return "not production; remains in internal review or third-party test package"
    if entry.get("evaluation_status") != "passed":
        return "evaluation has not passed"
    if entry.get("external_api_status") not in {"none", "optional_disabled"}:
        return "external API status blocks default generation"
    if entry.get("secret_status") != "not_required":
        return "secret-bound skill cannot enter default chain"
    if not entry.get("default_enabled"):
        return "not enabled for default chain"
    return "blocked by internal governance policy"


def list_internal_skill_registry() -> list[dict[str, Any]]:
    entries = []
    for raw_entry in _INTERNAL_SKILL_REGISTRY:
        entry = deepcopy(raw_entry)
        entry["default_generation_enabled"] = _is_allowed_in_default_generation_chain(entry)
        entry["admission_reason"] = _admission_reason(entry)
        entries.append(entry)
    return entries


def get_default_generation_skill_ids() -> list[str]:
    return [
        entry["skill_id"]
        for entry in list_internal_skill_registry()
        if entry["default_generation_enabled"]
    ]


def is_skill_allowed_in_default_generation(skill_id: str) -> bool:
    return skill_id in set(get_default_generation_skill_ids())


def build_internal_skill_governance_snapshot() -> dict[str, Any]:
    entries = list_internal_skill_registry()
    default_chain_skill_ids = [
        entry["skill_id"] for entry in entries if entry["default_generation_enabled"]
    ]
    blocked_skill_ids = [
        entry["skill_id"] for entry in entries if not entry["default_generation_enabled"]
    ]
    external_api_skill_ids = [
        entry["skill_id"] for entry in entries if entry["external_api_status"] != "none"
    ]
    secret_bound_skill_ids = [
        entry["skill_id"] for entry in entries if entry["secret_status"] != "not_required"
    ]
    data_egress_modes = sorted({entry["data_boundary"] for entry in entries})
    unreviewed_default_chain_count = sum(
        1
        for entry in entries
        if entry["default_generation_enabled"] and entry["evaluation_status"] != "passed"
    )

    return {
        "registry_version": REGISTRY_VERSION,
        "summary": {
            "total_skills": len(entries),
            "production_skills": sum(1 for entry in entries if entry["stage"] == "production"),
            "evaluated_skills": sum(1 for entry in entries if entry["evaluation_status"] == "passed"),
            "default_chain_skills": len(default_chain_skill_ids),
            "blocked_from_default_chain": len(blocked_skill_ids),
            "external_api_skills": len(external_api_skill_ids),
            "secret_required_skills": len(secret_bound_skill_ids),
            "data_egress_modes": data_egress_modes,
        },
        "diagnostics": {
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "default_chain_blocking_enforced": True,
            "unreviewed_default_chain_count": unreviewed_default_chain_count,
            "external_api_status_visible": True,
            "secret_status_visible": True,
            "data_egress_status_visible": True,
            "secret_values_exposed": False,
            "external_api_skill_ids": external_api_skill_ids,
            "secret_bound_skill_ids": secret_bound_skill_ids,
            "data_egress_modes": data_egress_modes,
        },
        "default_chain_skill_ids": default_chain_skill_ids,
        "blocked_from_default_chain_skill_ids": blocked_skill_ids,
        "entries": entries,
    }
