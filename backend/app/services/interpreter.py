from __future__ import annotations

from app.services.llm_parser import InsightResult, parse_insight_response
from app.core.config import get_settings
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_service import LLMService, get_llm_service

settings = get_settings()


class Interpreter:
    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    def interpret(
        self,
        *,
        title: str,
        source_domain: str,
        short_summary: str,
        long_summary: str,
        clean_content: str,
        output_language: str = "zh-CN",
    ) -> InsightResult:
        resolved_language = normalize_output_language(output_language)
        raw = self.llm_service.run_prompt(
            "interpret.txt",
            {
                "title": title,
                "source_domain": source_domain,
                "short_summary": short_summary,
                "long_summary": long_summary,
                "clean_content": clean_content,
                "output_language": resolved_language,
                "output_language_name": describe_output_language(resolved_language),
                "__timeout_seconds": str(settings.interpret_llm_timeout_seconds),
            },
        )
        return parse_insight_response(raw, output_language=resolved_language)
