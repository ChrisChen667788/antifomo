from __future__ import annotations

from app.services.llm_parser import SessionSummaryResult, parse_session_summary_response
from app.services.language import describe_output_language, normalize_output_language
from app.services.llm_service import LLMService, get_llm_service


class SessionSummarizer:
    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or get_llm_service()

    def summarize(
        self,
        *,
        goal_text: str,
        session_items_summary_list: str,
        output_language: str = "zh-CN",
    ) -> SessionSummaryResult:
        resolved_language = normalize_output_language(output_language)
        raw = self.llm_service.run_prompt(
            "session_summary.txt",
            {
                "goal_text": goal_text,
                "session_items_summary_list": session_items_summary_list,
                "output_language": resolved_language,
                "output_language_name": describe_output_language(resolved_language),
            },
        )
        return parse_session_summary_response(raw, output_language=resolved_language)
