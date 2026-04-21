from __future__ import annotations

from app.services.llm_parser import ScoreResult, parse_score_response
from app.core.config import get_settings
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_service import LLMService, get_llm_service

settings = get_settings()


class Scorer:
    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    def score(
        self,
        *,
        title: str,
        source_domain: str,
        short_summary: str,
        long_summary: str,
        output_language: str = "zh-CN",
        timeout_seconds: int | None = None,
    ) -> ScoreResult:
        resolved_language = normalize_output_language(output_language)
        resolved_timeout = max(1, int(timeout_seconds or settings.item_llm_timeout_seconds))
        raw = self.llm_service.run_prompt(
            "score.txt",
            {
                "title": title,
                "source_domain": source_domain,
                "short_summary": short_summary,
                "long_summary": long_summary,
                "output_language": resolved_language,
                "output_language_name": describe_output_language(resolved_language),
                "__timeout_seconds": str(resolved_timeout),
            },
        )
        return parse_score_response(raw, output_language=resolved_language)
