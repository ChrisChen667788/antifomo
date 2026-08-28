from __future__ import annotations

from app.core.config import BACKEND_DIR, Settings


def test_env_example_accepts_blank_optional_model_prices(monkeypatch) -> None:
    """A clean CI checkout copies this file before importing application code."""

    for key in (
        "OPENAI_INPUT_COST_PER_MILLION",
        "OPENAI_CACHED_INPUT_COST_PER_MILLION",
        "OPENAI_OUTPUT_COST_PER_MILLION",
        "STRATEGY_OPENAI_INPUT_COST_PER_MILLION",
        "STRATEGY_OPENAI_CACHED_INPUT_COST_PER_MILLION",
        "STRATEGY_OPENAI_OUTPUT_COST_PER_MILLION",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=BACKEND_DIR / ".env.example")

    assert settings.openai_input_cost_per_million is None
    assert settings.openai_cached_input_cost_per_million is None
    assert settings.openai_output_cost_per_million is None
    assert settings.strategy_openai_input_cost_per_million is None
    assert settings.strategy_openai_cached_input_cost_per_million is None
    assert settings.strategy_openai_output_cost_per_million is None
