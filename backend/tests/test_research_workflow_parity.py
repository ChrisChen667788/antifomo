from __future__ import annotations

from app.services.research.evaluation_dataset import load_research_evaluation_dataset
from app.services.research.workflow_parity import run_research_workflow_parity


def test_locked_dataset_passes_full_offline_workflow_parity_gate() -> None:
    manifest, cases = load_research_evaluation_dataset()

    result = run_research_workflow_parity(manifest, cases)

    assert result.selected_case_count == 100
    assert result.passed_case_count == 100
    assert result.failed_case_count == 0
    assert result.parity_rate == 1.0
    assert result.production_gate_eligible is True
    assert result.production_gate_passed is True
    assert result.gate_blockers == []
