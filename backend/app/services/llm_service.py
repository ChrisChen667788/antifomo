from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import get_settings
from app.services.legacy_openai_adapter import OpenAILLMService, extract_openai_message_content
from app.services.llm_fallback_service import FallbackLLMService, run_llm_prompt_result
from app.services.llm_protocol import LLMService
from app.services.llm_provider_router import LLMProviderRouter
from app.services.mock_llm_provider import MockLLMService


# Compatibility facade: application callers keep this stable import path while
# provider implementations and routing live in their owner modules.
def build_llm_service(*, role: str = "generation", settings: Any | None = None) -> LLMService | None:
    return LLMProviderRouter(settings or get_settings()).build(role)


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    service = build_llm_service()
    return service or MockLLMService()


@lru_cache(maxsize=1)
def get_strategy_llm_service() -> LLMService | None:
    return build_llm_service(role="strategy")


@lru_cache(maxsize=1)
def get_research_llm_service() -> LLMService:
    service = build_llm_service(role="research_generation")
    if service is None:
        raise RuntimeError("Research generation LLM is not configured; mock fallback is disabled")
    return service


__all__ = [
    "FallbackLLMService",
    "LLMProviderRouter",
    "LLMService",
    "MockLLMService",
    "OpenAILLMService",
    "build_llm_service",
    "extract_openai_message_content",
    "get_llm_service",
    "get_research_llm_service",
    "get_strategy_llm_service",
    "run_llm_prompt_result",
]
