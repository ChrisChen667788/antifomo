from app.services.llm_service import FallbackLLMService, extract_openai_message_content
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
