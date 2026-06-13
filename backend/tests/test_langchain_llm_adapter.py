from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.langchain_llm_adapter import LangChainOpenAIAdapter
from app.services.llm_parser import SummarizeResult
from app.services.llm_runtime import ModelPricing
from app.services.llm_service import LLMProviderRouter, MockLLMService


def _raw_message() -> SimpleNamespace:
    return SimpleNamespace(
        content="",
        id="response-123",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "input_token_details": {"cache_read": 20},
        },
        response_metadata={"model_name": "gpt-test-2026", "finish_reason": "stop"},
    )


class _StructuredRunnable:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response

    def invoke(self, prompt: str) -> dict[str, Any]:
        assert "测试标题" in prompt
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class _FakeChatModel:
    def __init__(self, responses: dict[str, dict[str, Any] | Exception]) -> None:
        self.responses = responses
        self.methods: list[str] = []

    def with_structured_output(
        self,
        schema: type,
        *,
        method: str,
        include_raw: bool,
    ) -> _StructuredRunnable:
        assert schema is SummarizeResult
        assert include_raw is True
        self.methods.append(method)
        return _StructuredRunnable(self.responses[method])


def _variables() -> dict[str, str]:
    return {
        "title": "测试标题",
        "source_domain": "example.com",
        "clean_content": "这是用于验证 LangChain 结构化输出适配器的正文。",
        "output_language": "zh-CN",
        "output_language_name": "简体中文",
    }


def test_langchain_adapter_returns_structured_json_usage_and_cost() -> None:
    parsed = SummarizeResult(
        display_title="测试标题",
        short_summary="结构化摘要",
        long_summary="结构化长摘要",
        key_points=["要点一"],
    )
    fake_model = _FakeChatModel(
        {"json_schema": {"raw": _raw_message(), "parsed": parsed, "parsing_error": None}}
    )
    adapter = LangChainOpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        temperature=0.1,
        timeout_seconds=30,
        pricing=ModelPricing(
            input_cost_per_million=2.0,
            cached_input_cost_per_million=0.5,
            output_cost_per_million=8.0,
        ),
        chat_model=fake_model,
    )

    result = adapter.run_prompt_result("summarize.txt", _variables())

    assert json.loads(result.content)["short_summary"] == "结构化摘要"
    assert result.provider == "langchain_openai"
    assert result.model == "gpt-test-2026"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.usage.cached_input_tokens == 20
    assert result.usage.source == "provider"
    assert result.estimated_cost_usd == pytest.approx(0.00057)
    assert result.response_id == "response-123"
    assert result.finish_reason == "stop"
    assert fake_model.methods == ["json_schema"]


def test_langchain_adapter_falls_back_to_json_mode() -> None:
    parsed = SummarizeResult(short_summary="fallback summary")
    fake_model = _FakeChatModel(
        {
            "json_schema": RuntimeError("gateway does not support response_format json_schema"),
            "json_mode": {"raw": _raw_message(), "parsed": parsed, "parsing_error": None},
        }
    )
    adapter = LangChainOpenAIAdapter(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        temperature=0.1,
        timeout_seconds=30,
        chat_model=fake_model,
    )

    result = adapter.run_prompt_result("summarize.txt", _variables())

    assert result.attempts == 2
    assert result.metadata["structured_output_method"] == "json_mode"
    assert result.metadata["structured_output_fallback_reason"] == "RuntimeError"
    assert fake_model.methods == ["json_schema", "json_mode"]


def test_provider_router_selects_langchain_and_preserves_mock_without_key() -> None:
    configured = Settings(
        _env_file=None,
        llm_provider="langchain",
        llm_fallback_to_mock=False,
        openai_api_key="test-key",
    )
    service = LLMProviderRouter(configured).build()
    assert isinstance(service, LangChainOpenAIAdapter)

    missing_key = Settings(
        _env_file=None,
        llm_provider="langchain_openai",
        llm_fallback_to_mock=False,
        openai_api_key=None,
    )
    assert isinstance(LLMProviderRouter(missing_key).build(), MockLLMService)


def test_settings_reject_invalid_provider_and_negative_pricing() -> None:
    with pytest.raises(ValueError, match="LLM provider"):
        Settings(_env_file=None, llm_provider="unknown")
    with pytest.raises(ValueError, match="non-negative"):
        Settings(_env_file=None, openai_input_cost_per_million=-1)
