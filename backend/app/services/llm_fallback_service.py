from __future__ import annotations

from dataclasses import replace
import logging
from typing import Any

from app.services.llm_protocol import LLMService
from app.services.llm_runtime import LLMRunResult, estimated_usage
from app.services.prompt_loader import render_prompt

def _service_run_result(service: Any, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
    run_result = getattr(service, "run_prompt_result", None)
    if callable(run_result):
        result = run_result(prompt_name, variables)
        if isinstance(result, LLMRunResult):
            return result
        raise RuntimeError("LLM result service returned an invalid result")
    content = service.run_prompt(prompt_name, variables)
    runtime_variables = {key: value for key, value in variables.items() if not key.startswith("__")}
    prompt = render_prompt(prompt_name, runtime_variables)
    return LLMRunResult(
        content=content,
        provider=str(getattr(service, "provider", "") or service.__class__.__name__),
        model=str(getattr(service, "model", "") or "unspecified"),
        usage=estimated_usage(prompt, content),
        metadata={"compatibility_adapter": True},
    )


def run_llm_prompt_result(service: Any, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
    return _service_run_result(service, prompt_name, variables)


class FallbackLLMService:
    def __init__(
        self,
        primary: LLMService,
        fallback: LLMService,
        *,
        logger_name: str = "anti_fomo.llm",
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.logger = logging.getLogger(logger_name)

    def run_prompt_result(self, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
        try:
            return _service_run_result(self.primary, prompt_name, variables)
        except Exception as exc:
            self.logger.warning(
                "Primary LLM failed for prompt=%s, using fallback service: %s",
                prompt_name,
                exc,
            )
            fallback_result = _service_run_result(self.fallback, prompt_name, variables)
            return replace(
                fallback_result,
                status="fallback",
                attempts=fallback_result.attempts + 1,
                metadata={
                    **fallback_result.metadata,
                    "fallback_used": True,
                    "primary_provider": str(
                        getattr(self.primary, "provider", "") or self.primary.__class__.__name__
                    ),
                    "primary_error": exc.__class__.__name__,
                },
            )

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return self.run_prompt_result(prompt_name, variables).content

