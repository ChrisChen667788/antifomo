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


class _Response:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.payload.encode()

    def __iter__(self):
        return iter(line.encode() for line in self.payload.splitlines(keepends=True))


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


def test_render_prompt_replaces_whitespace_padded_strategy_variables() -> None:
    rendered = render_prompt(
        "research_strategy_refine.txt",
        {
            "keyword": "杭州智慧文旅",
            "research_focus": "核验采购信号",
            "output_language": "zh-CN",
            "scope_hints": '{"regions":["杭州"]}',
            "source_intelligence": '{"target_accounts":["杭州市文化广电旅游局"]}',
            "current_report": '{"report_title":"待优化"}',
        },
    )

    assert "{{" not in rendered
    assert "杭州市文化广电旅游局" in rendered


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


def test_research_prompt_forbids_entity_padding_and_internal_metrics_in_customer_copy() -> None:
    rendered = render_prompt("research_report.txt", {})

    assert "不足 3 个时允许少于 3 个或空数组" in rendered
    assert "不得把这些名称写入报告或声称“来自用户候选池”" in rendered
    assert "内部流水线指标不得写进客户正文" in rendered


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


def test_legacy_openai_retries_share_one_total_timeout(monkeypatch) -> None:
    service = OpenAILLMService(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="configured-model",
        temperature=0.1,
        timeout_seconds=10,
    )
    recorded_timeouts: list[float] = []
    ticks = iter([0.0, 0.0, 3.0, 4.0])

    def fake_urlopen(*_args, timeout: float, **_kwargs):
        recorded_timeouts.append(timeout)
        if len(recorded_timeouts) == 1:
            raise TimeoutError("timed out")
        return _Response('{"choices":[{"message":{"content":"{}"}}]}')

    monkeypatch.setattr(legacy_openai_adapter.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(legacy_openai_adapter.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(legacy_openai_adapter.request, "urlopen", fake_urlopen)

    _, attempts = service._make_request("prompt", 10, None, 2)

    assert attempts == 2
    assert recorded_timeouts == [10.0, 6.0]


def test_legacy_openai_streams_long_report_and_applies_output_limit(monkeypatch) -> None:
    service = OpenAILLMService(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="configured-model",
        temperature=0.1,
        timeout_seconds=30,
    )
    captured_payload: dict[str, object] = {}
    stream = "\n".join(
        [
            'data: {"id":"chatcmpl-stream","model":"resolved-model","choices":[{"delta":{"content":"{\\\"report_title\\\":\\\""},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-stream","model":"resolved-model","choices":[{"delta":{"content":"测试\\\"}"},"finish_reason":"stop"}]}',
            "data: [DONE]",
        ]
    )

    def fake_urlopen(req, **_kwargs):
        captured_payload.update(json.loads(req.data.decode()))
        return _Response(stream)

    monkeypatch.setattr(legacy_openai_adapter.request, "urlopen", fake_urlopen)
    result = service.run_prompt_result(
        "research_report.txt",
        {
            "keyword": "测试",
            "__stream_response": "true",
            "__max_output_tokens": "7000",
        },
    )

    assert result.content == '{"report_title":"测试"}'
    assert result.model == "resolved-model"
    assert result.response_id == "chatcmpl-stream"
    assert result.finish_reason == "stop"
    assert result.usage.source == "estimated"
    assert result.metadata["streamed"] is True
    assert result.metadata["max_output_tokens"] == 7000
    assert captured_payload["stream"] is True
    assert captured_payload["max_tokens"] == 7000


def test_legacy_openai_stream_ignores_reasoning_and_collects_usage() -> None:
    service = OpenAILLMService(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        model="configured-model",
        temperature=0.1,
        timeout_seconds=30,
    )
    stream = _Response(
        "\n".join(
            [
                'data: {"choices":[{"delta":{"reasoning_content":"internal"},"finish_reason":null}]}',
                'data: {"choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}',
                'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}',
                "data: [DONE]",
            ]
        )
    )

    body = service._consume_stream_response(stream, deadline=float("inf"))
    payload = json.loads(body)

    assert payload["choices"][0]["message"]["content"] == "{}"
    assert payload["usage"]["total_tokens"] == 12
