from __future__ import annotations

from typing import Any

from app.services.legacy_openai_adapter import OpenAILLMService
from app.services.llm_fallback_service import FallbackLLMService
from app.services.llm_protocol import LLMService
from app.services.llm_runtime import ModelPricing
from app.services.mock_llm_provider import MockLLMService

class LLMProviderRouter:
    def __init__(self, settings: Any) -> None:
        self.settings = settings

    def _pricing(self, role: str) -> ModelPricing:
        prefix = "strategy_openai" if role == "strategy" else "openai"
        return ModelPricing(
            input_cost_per_million=getattr(self.settings, f"{prefix}_input_cost_per_million"),
            cached_input_cost_per_million=getattr(
                self.settings,
                f"{prefix}_cached_input_cost_per_million",
            ),
            output_cost_per_million=getattr(self.settings, f"{prefix}_output_cost_per_million"),
        )

    def _route(self, role: str) -> dict[str, Any]:
        strategy = role == "strategy"
        return {
            "provider": self.settings.strategy_llm_provider if strategy else self.settings.llm_provider,
            "api_key": self.settings.strategy_openai_api_key if strategy else self.settings.openai_api_key,
            "fallback_api_key": (
                self.settings.strategy_openai_fallback_api_key
                if strategy
                else self.settings.openai_fallback_api_key
            ),
            "base_url": self.settings.strategy_openai_base_url if strategy else self.settings.openai_base_url,
            "model": self.settings.strategy_openai_model if strategy else self.settings.openai_model,
            "temperature": (
                self.settings.strategy_openai_temperature if strategy else self.settings.openai_temperature
            ),
            "timeout_seconds": (
                self.settings.strategy_openai_timeout_seconds if strategy else self.settings.openai_timeout_seconds
            ),
            "max_retries": (
                self.settings.strategy_llm_max_retries if strategy else self.settings.llm_max_retries
            ),
            "pricing": self._pricing(role),
        }

    def _langchain_service(self, route: dict[str, Any], *, api_key: str) -> LLMService:
        from app.services.langchain_llm_adapter import LangChainOpenAIAdapter

        fallback_method = self.settings.langchain_structured_output_fallback_method
        return LangChainOpenAIAdapter(
            api_key=api_key,
            base_url=route["base_url"],
            model=route["model"],
            temperature=route["temperature"],
            timeout_seconds=route["timeout_seconds"],
            pricing=route["pricing"],
            organization=self.settings.openai_organization,
            project=self.settings.openai_project,
            verify_ssl=self.settings.openai_verify_ssl,
            ca_bundle=self.settings.openai_ca_bundle,
            max_retries=route["max_retries"],
            structured_output_method=self.settings.langchain_structured_output_method or "json_schema",
            structured_output_fallback_method=fallback_method,
        )

    def _remote_service(self, route: dict[str, Any]) -> LLMService:
        provider = route["provider"]
        api_key = str(route["api_key"] or "")
        if provider == "langchain_openai":
            primary = self._langchain_service(route, api_key=api_key)
            secondary_key = str(route["fallback_api_key"] or "")
            if secondary_key:
                return FallbackLLMService(
                    primary,
                    self._langchain_service(route, api_key=secondary_key),
                )
            return primary
        return OpenAILLMService(
            api_key=api_key,
            base_url=route["base_url"],
            model=route["model"],
            temperature=route["temperature"],
            timeout_seconds=route["timeout_seconds"],
            organization=self.settings.openai_organization,
            project=self.settings.openai_project,
            verify_ssl=self.settings.openai_verify_ssl,
            ca_bundle=self.settings.openai_ca_bundle,
            fallback_api_key=route["fallback_api_key"],
            pricing=route["pricing"],
        )

    def build(self, role: str = "generation") -> LLMService | None:
        route = self._route(role)
        provider = route["provider"]
        mock_service = MockLLMService()
        if provider == "mock":
            return mock_service
        if not route["api_key"]:
            return None if role in {"strategy", "research_generation"} else mock_service
        service = self._remote_service(route)
        if role == "research_generation":
            if self.settings.research_llm_fallback_to_mock:
                return FallbackLLMService(service, mock_service)
            return service
        if role != "strategy" and self.settings.llm_fallback_to_mock:
            return FallbackLLMService(service, mock_service)
        return service
