from __future__ import annotations

from app.services.llm_parser import SummarizeResult, parse_summarize_response
from app.core.config import get_settings
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_service import LLMService, get_llm_service

settings = get_settings()


class Summarizer:
    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    def summarize(
        self,
        *,
        title: str,
        source_domain: str,
        clean_content: str,
        output_language: str = "zh-CN",
    ) -> SummarizeResult:
        resolved_language = normalize_output_language(output_language)
        raw = self.llm_service.run_prompt(
            "summarize.txt",
            {
                "title": title,
                "source_domain": source_domain,
                "clean_content": clean_content,
                "output_language": resolved_language,
                "output_language_name": describe_output_language(resolved_language),
                "__timeout_seconds": str(settings.item_llm_timeout_seconds),
            },
        )
        return parse_summarize_response(raw, output_language=resolved_language)
