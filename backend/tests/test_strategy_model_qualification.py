from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.strategy_model_qualification_service import (
    load_strategy_model_qualification,
    run_strategy_model_qualification,
)


def _output(*, strong: bool) -> str:
    if strong:
        return json.dumps(
            {
                "report_title": "杭州｜智慧文旅｜杭州市文化广电旅游局：采购信号与推进路径",
                "executive_summary": "南京市数据局与杭州项目均应围绕公开招标、游客服务、知识检索、数据安全和人工复核核验证据。",
                "consulting_angle": "并行对接主管部门并验证最小试点，形成可执行推进工作流。",
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "report_title": "行业研究分析",
            "executive_summary": "建议继续关注。",
            "consulting_angle": "持续推进。",
        },
        ensure_ascii=False,
    )


def test_fixed_evidence_qualification_persists_and_reloads_gate(tmp_path: Path) -> None:
    path = tmp_path / "strategy.json"

    def runner(model: str, _prompt: str, _variables: dict[str, str]) -> str:
        return _output(strong=model == "candidate")

    result = run_strategy_model_qualification(
        SimpleNamespace(),
        baseline_model="baseline",
        candidate_model="candidate",
        runner=runner,
        artifact_path=path,
    )

    assert result["status"] == "pass"
    assert result["results"]["candidate"]["average_score"] >= 80
    assert load_strategy_model_qualification(
        baseline_model="baseline",
        candidate_model="candidate",
        artifact_path=path,
    ) is not None


def test_fixed_evidence_qualification_blocks_weaker_candidate(tmp_path: Path) -> None:
    path = tmp_path / "strategy.json"

    result = run_strategy_model_qualification(
        SimpleNamespace(),
        baseline_model="baseline",
        candidate_model="candidate",
        runner=lambda model, _prompt, _variables: _output(strong=model == "baseline"),
        artifact_path=path,
    )

    assert result["status"] == "blocked"
    assert load_strategy_model_qualification(
        baseline_model="baseline",
        candidate_model="candidate",
        artifact_path=path,
    ) is None
