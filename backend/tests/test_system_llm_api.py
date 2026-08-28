from __future__ import annotations

from app.api import system
from app.core.config import Settings
from app.services.llm_runtime import LLMRunResult


def test_llm_dry_run_exposes_route_usage_and_model(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        openai_input_cost_per_million=1.5,
        openai_output_cost_per_million=6.0,
    )
    monkeypatch.setattr(system, "settings", settings)

    response = system.llm_dry_run(
        system.LLMDryRunRequest(
            prompt_name="summarize.txt",
            variables={
                "title": "测试标题",
                "source_domain": "example.com",
                "clean_content": "用于系统诊断接口的测试正文。",
            },
        )
    )

    assert response.ok is True
    assert response.provider_used == "mock"
    assert response.model == "deterministic-mock"
    assert response.usage["source"] == "estimated"
    assert response.usage["total_tokens"] > 0
    assert response.parsed_preview["display_title"]

    config = system.get_llm_config()
    assert config["openai_pricing_configured"] is True
    assert config["openai_pricing_per_million_usd"]["input"] == 1.5


def test_llm_dry_run_marks_fallback_api_key_usage(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="openai",
        openai_api_key="primary-key",
        openai_fallback_api_key="fallback-key",
    )
    monkeypatch.setattr(system, "settings", settings)
    monkeypatch.setattr(system, "build_llm_service", lambda **_kwargs: object())
    monkeypatch.setattr(
        system,
        "run_llm_prompt_result",
        lambda *_args, **_kwargs: LLMRunResult(
            content="{}",
            provider="openai",
            model="gpt-5.5",
            metadata={"fallback_api_key_used": True},
        ),
    )
    monkeypatch.setattr(system, "_parse_by_prompt_name", lambda *_args: {})

    response = system.llm_dry_run(system.LLMDryRunRequest())

    assert response.ok is True
    assert response.fallback_used is True
