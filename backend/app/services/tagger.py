from __future__ import annotations

from app.services.llm_parser import TagsResult, parse_tags_response
from app.core.config import get_settings
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_service import LLMService, get_llm_service

settings = get_settings()


class Tagger:
    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    def extract_tags(
        self,
        *,
        title: str,
        short_summary: str,
        clean_content: str,
        output_language: str = "zh-CN",
    ) -> TagsResult:
        resolved_language = normalize_output_language(output_language)
        raw = self.llm_service.run_prompt(
            "tags.txt",
            {
                "title": title,
                "short_summary": short_summary,
                "clean_content": clean_content,
                "output_language": resolved_language,
                "output_language_name": describe_output_language(resolved_language),
                "__timeout_seconds": str(settings.item_llm_timeout_seconds),
            },
        )
        return parse_tags_response(raw, output_language=resolved_language)
