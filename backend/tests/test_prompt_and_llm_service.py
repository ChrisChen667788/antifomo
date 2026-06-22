import json

from app.services import legacy_openai_adapter
from app.services.llm_runtime import ModelPricing
from app.services.llm_service import FallbackLLMService, OpenAILLMService, extract_openai_message_content
from app.services.prompt_loader import render_prompt


class _BrokenService:
    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        raise RuntimeError("boom")


class _StaticService:
    def __init__(self, value: str) -> None:
        self.value = value

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return self.value


def test_render_prompt_replaces_variables() -> None:
    rendered = render_prompt(
        "summarize.txt",
        {
            "title": "测试标题",
            "source_domain": "example.com",
            "clean_content": "正文内容",
        },
    )
    assert "{{title}}" not in rendered
    assert "测试标题" in rendered
    assert "example.com" in rendered


def test_render_interpret_prompt_replaces_variables() -> None:
    rendered = render_prompt(
        "interpret.txt",
        {
            "title": "测试标题",
            "source_domain": "example.com",
            "short_summary": "短摘要",
            "long_summary": "长摘要",
            "clean_content": "正文内容",
        },
    )
    assert "{{title}}" not in rendered
    assert "测试标题" in rendered
    assert "正文内容" in rendered


def test_extract_openai_message_content_string() -> None:
    response = {
        "choices": [
            {"message": {"content": '{"short_summary":"ok"}'}}
        ]
    }
    assert extract_openai_message_content(response) == '{"short_summary":"ok"}'


def test_extract_openai_message_content_list_blocks() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "output_text", "text": '{"a":1}'},
                        {"type": "output_text", "text": '{"b":2}'},
                    ]
                }
            }
        ]
    }
    assert extract_openai_message_content(response) == '{"a":1}\n{"b":2}'


def test_fallback_llm_service() -> None:
    service = FallbackLLMService(_BrokenService(), _StaticService('{"ok":true}'))
    assert service.run_prompt("summarize.txt", {}) == '{"ok":true}'
    result = service.run_prompt_result("summarize.txt", {})
    assert result.status == "fallback"
    assert result.metadata["fallback_used"] is True


def test_legacy_openai_service_exposes_provider_usage_and_pricing() -> None:
    service = OpenAILLMService(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="configured-model",
        temperature=0.1,
        timeout_seconds=30,
        pricing=ModelPricing(input_cost_per_million=1.0, output_cost_per_million=4.0),
    )
    response = {
        "id": "chatcmpl-test",
        "model": "resolved-model",
        "choices": [
            {
                "message": {"content": '{"short_summary":"ok"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 80,
            "completion_tokens": 20,
            "total_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 10},
        },
    }
    service._make_request = lambda *args, **kwargs: (json.dumps(response), 1)  # type: ignore[method-assign]

    result = service.run_prompt_result(
        "summarize.txt",
        {"title": "测试", "source_domain": "example.com", "clean_content": "正文"},
    )

    assert result.model == "resolved-model"
    assert result.usage.input_tokens == 80
    assert result.usage.output_tokens == 20
    assert result.usage.cached_input_tokens == 10
    assert result.usage.source == "provider"
    assert result.estimated_cost_usd == 0.00016


def test_legacy_openai_service_switches_to_fallback_key_on_quota_error() -> None:
    service = OpenAILLMService(
        api_key="primary-key",
        fallback_api_key="fallback-key",
        base_url="https://api.example.com/v1",
        model="configured-model",
        temperature=0.1,
        timeout_seconds=30,
    )
    response = {
        "id": "chatcmpl-fallback",
        "model": "resolved-model",
        "choices": [{"message": {"content": '{"short_summary":"ok"}'}, "finish_reason": "stop"}],
    }
    calls: list[str] = []

    def fake_request(*args, **kwargs):
        calls.append(service._active_api_key())
        if len(calls) == 1:
            raise legacy_openai_adapter._QuotaExhaustedError("quota exceeded")
        return json.dumps(response), 1

    service._make_request = fake_request  # type: ignore[method-assign]
    result = service.run_prompt_result(
        "summarize.txt",
        {"title": "测试", "source_domain": "example.com", "clean_content": "正文"},
    )

    assert calls == ["primary-key", "fallback-key"]
    assert result.metadata["fallback_api_key_used"] is True


def test_legacy_openai_service_detects_chinese_quota_exhaustion() -> None:
    assert OpenAILLMService._is_quota_error(
        401,
        '{"message":"该令牌额度已用尽 !token.UnlimitedQuota"}',
    )
