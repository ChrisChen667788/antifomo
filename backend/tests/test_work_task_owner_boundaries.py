from __future__ import annotations

from pathlib import Path


def test_work_task_owner_modules_do_not_import_compatibility_facade() -> None:
    services_dir = Path(__file__).resolve().parents[1] / "app" / "services"
    for relative_path in (
        "work_tasks/context.py",
        "work_tasks/pdf.py",
        "work_tasks/formal_documents.py",
    ):
        source = (services_dir / relative_path).read_text(encoding="utf-8")
        assert "work_task_service" not in source


def test_task_runtime_uses_formal_document_owners_directly() -> None:
    services_dir = Path(__file__).resolve().parents[1] / "app" / "services"
    source = (services_dir / "task_runtime.py").read_text(encoding="utf-8")

    assert "from app.services.work_tasks.context import sanitize_task_context_payload" in source
    assert "from app.services.work_tasks.formal_documents import (" in source


def test_knowledge_intelligence_owner_modules_do_not_import_compatibility_service() -> None:
    services_dir = Path(__file__).resolve().parents[1] / "app" / "services"
    for relative_path in (
        "knowledge_intelligence/commercial_text.py",
        "knowledge_intelligence/entity_quality.py",
        "knowledge_intelligence/report_metadata.py",
    ):
        source = (services_dir / relative_path).read_text(encoding="utf-8")
        assert "knowledge_intelligence_service" not in source

    facade_source = (services_dir / "knowledge_intelligence_service.py").read_text(encoding="utf-8")
    assert "from app.services.knowledge_intelligence.entity_quality import (" in facade_source
    assert "from app.services.knowledge_intelligence.report_metadata import (" in facade_source
