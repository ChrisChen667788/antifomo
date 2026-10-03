from __future__ import annotations

from app.services.llm_parser import SummarizeResult, parse_summarize_response_with_status
from app.core.config import get_settings
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_runtime import serialize_llm_failure, serialize_llm_run_result
from app.services.llm_service import LLMService, get_llm_service, run_llm_prompt_result

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
        timeout_seconds: int | None = None,
    ) -> SummarizeResult:
        resolved_language = normalize_output_language(output_language)
        resolved_timeout = max(1, int(timeout_seconds or settings.item_llm_timeout_seconds))
        prompt_variables = {
            "title": title,
            "source_domain": source_domain,
            "clean_content": clean_content,
            "output_language": resolved_language,
            "output_language_name": describe_output_language(resolved_language),
            "__timeout_seconds": str(resolved_timeout),
        }
        try:
            run_result = run_llm_prompt_result(
                self.llm_service,
                "summarize.txt",
                prompt_variables,
            )
        except Exception as exc:
            exc._runtime_receipt = serialize_llm_failure(  # type: ignore[attr-defined]
                exc,
                prompt_name="summarize.txt",
                prompt_variables=prompt_variables,
                provider=str(getattr(self.llm_service, "provider", "unknown")),
                model=str(getattr(self.llm_service, "model", "unknown")),
            )
            raise
        parsed, parse_degraded = parse_summarize_response_with_status(
            run_result.content,
            output_language=resolved_language,
        )
        parsed._parse_degraded = parse_degraded
        parsed._runtime_receipt = serialize_llm_run_result(
            run_result,
            prompt_name="summarize.txt",
            parse_degraded=parse_degraded,
            prompt_variables=prompt_variables,
        )
        return parsed
