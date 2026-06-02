from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES = REPO_ROOT / "backend" / "app" / "services"
DELIVERY_MODULES = (
    SERVICES / "delivery" / "market_intelligence.py",
    SERVICES / "delivery" / "solution_architecture.py",
    SERVICES / "delivery" / "solution_materials.py",
)
SOLUTION_ORCHESTRATOR = SERVICES / "research_solution_intelligence_service.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_delivery_modules_do_not_depend_on_solution_orchestrator_or_api_layer() -> None:
    forbidden = {
        "app.api",
        "app.api.research",
        "app.services.research_solution_intelligence_service",
    }

    for module_path in DELIVERY_MODULES:
        imports = _imports(module_path)
        violations = sorted(
            imported
            for imported in imports
            if imported in forbidden or any(imported.startswith(f"{prefix}.") for prefix in forbidden)
        )
        assert violations == [], f"{module_path.name} has forbidden imports: {violations}"


def test_solution_delivery_orchestrator_stays_thin_and_delegates_domain_work() -> None:
    source = SOLUTION_ORCHESTRATOR.read_text(encoding="utf-8")
    imports = _imports(SOLUTION_ORCHESTRATOR)

    assert len(source.splitlines()) <= 220
    assert "app.services.delivery.market_intelligence" in imports
    assert "app.services.delivery.solution_architecture" in imports
    assert "app.services.delivery.solution_materials" in imports
    assert "def build_solution_delivery_markdown(" not in source
    assert "def build_advisory_artifacts(" not in source
    assert "def build_market_intelligence_pack(" not in source
    assert "re.compile(" not in source
