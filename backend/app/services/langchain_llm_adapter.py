from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.services.llm_runtime import LLMRunResult, LLMUsage, ModelPricing, schema_for_prompt
from app.services.prompt_loader import render_prompt


StructuredOutputMethod = Literal["function_calling", "json_mode", "json_schema"]


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for block in content:
        if isinstance(block, str):
            chunks.append(block)
            continue
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()


def _usage_from_message(message: Any) -> LLMUsage:
    usage = getattr(message, "usage_metadata", None)
    if not isinstance(usage, dict):
        response_metadata = getattr(message, "response_metadata", None)
        token_usage = response_metadata.get("token_usage") if isinstance(response_metadata, dict) else None
        usage = token_usage if isinstance(token_usage, dict) else {}

    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    input_details = usage.get("input_token_details") or usage.get("prompt_tokens_details") or {}
    if not isinstance(input_details, dict):
        input_details = {}
    cached_input_tokens = int(
        input_details.get("cache_read")
        or input_details.get("cached_tokens")
        or usage.get("cache_read_input_tokens")
        or 0
    )
    cache_creation_input_tokens = int(
        input_details.get("cache_creation") or usage.get("cache_creation_input_tokens") or 0
    )
    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        source="provider" if input_tokens or output_tokens or total_tokens else "unavailable",
    )


def _structured_content(parsed: Any) -> str:
    if isinstance(parsed, BaseModel):
        return parsed.model_dump_json()
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False)
    raise RuntimeError("LangChain structured output returned no parsed payload")


class LangChainOpenAIAdapter:
    """LangChain adapter that keeps framework objects behind the LLM service boundary."""

    provider = "langchain_openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
        pricing: ModelPricing | None = None,
        organization: str | None = None,
        project: str | None = None,
        verify_ssl: bool = True,
        ca_bundle: str | None = None,
        max_retries: int = 1,
        structured_output_method: StructuredOutputMethod = "json_schema",
        structured_output_fallback_method: StructuredOutputMethod | None = "json_mode",
        chat_model: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.pricing = pricing or ModelPricing()
        self.organization = organization
        self.project = project
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle
        self.max_retries = max(0, max_retries)
        self.structured_output_method = structured_output_method
        self.structured_output_fallback_method = structured_output_fallback_method
        self._injected_chat_model = chat_model
        self._chat_models: dict[int, Any] = {}

    def _build_chat_model(self, timeout_seconds: int) -> Any:
        if self._injected_chat_model is not None:
            return self._injected_chat_model

        import httpx
        from langchain_openai import ChatOpenAI

        verify: bool | str = self.verify_ssl
        if self.verify_ssl and self.ca_bundle:
            verify = str(Path(self.ca_bundle).expanduser())
        default_headers = {"OpenAI-Project": self.project} if self.project else None
        return ChatOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            temperature=self.temperature,
            timeout=timeout_seconds,
            max_retries=self.max_retries,
            organization=self.organization,
            default_headers=default_headers,
            http_client=httpx.Client(verify=verify, timeout=timeout_seconds),
            http_async_client=httpx.AsyncClient(verify=verify, timeout=timeout_seconds),
            http_socket_options=(),
        )

    def _model_for_timeout(self, timeout_seconds: int) -> Any:
        if self._injected_chat_model is not None:
            return self._injected_chat_model
        model = self._chat_models.get(timeout_seconds)
        if model is None:
            model = self._build_chat_model(timeout_seconds)
            self._chat_models[timeout_seconds] = model
        return model

    @staticmethod
    def _response_metadata(message: Any) -> dict[str, Any]:
        value = getattr(message, "response_metadata", None)
        return value if isinstance(value, dict) else {}

    def _build_result(
        self,
        *,
        raw_message: Any,
        content: str,
        attempts: int,
        structured_method: str | None,
        fallback_reason: str = "",
    ) -> LLMRunResult:
        usage = _usage_from_message(raw_message)
        response_metadata = self._response_metadata(raw_message)
        actual_model = str(response_metadata.get("model_name") or response_metadata.get("model") or self.model)
        metadata: dict[str, object] = {
            "structured_output": bool(structured_method),
            "structured_output_method": structured_method or "none",
        }
        if fallback_reason:
            metadata["structured_output_fallback_reason"] = fallback_reason[:500]
        return LLMRunResult(
            content=content,
            provider=self.provider,
            model=actual_model,
            usage=usage,
            estimated_cost_usd=self.pricing.estimate_cost_usd(usage),
            attempts=attempts,
            response_id=str(getattr(raw_message, "id", "") or ""),
            finish_reason=str(response_metadata.get("finish_reason") or ""),
            metadata=metadata,
        )

    def _run_structured(
        self,
        *,
        chat_model: Any,
        prompt: str,
        schema: type[BaseModel],
        method: StructuredOutputMethod,
        attempts: int,
        fallback_reason: str = "",
    ) -> LLMRunResult:
        runnable = chat_model.with_structured_output(schema, method=method, include_raw=True)
        response = runnable.invoke(prompt)
        if not isinstance(response, dict):
            raise RuntimeError("LangChain structured output returned an invalid response envelope")
        parsing_error = response.get("parsing_error")
        if parsing_error is not None:
            raise RuntimeError(f"LangChain structured output parsing failed: {parsing_error}")
        raw_message = response.get("raw")
        if raw_message is None:
            raise RuntimeError("LangChain structured output returned no raw message")
        content = _structured_content(response.get("parsed"))
        return self._build_result(
            raw_message=raw_message,
            content=content,
            attempts=attempts,
            structured_method=method,
            fallback_reason=fallback_reason,
        )

    def run_prompt_result(self, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
        runtime_variables = dict(variables)
        timeout_override = runtime_variables.pop("__timeout_seconds", None)
        try:
            timeout_seconds = max(1, int(timeout_override)) if timeout_override is not None else self.timeout_seconds
        except (TypeError, ValueError):
            timeout_seconds = self.timeout_seconds
        prompt = render_prompt(prompt_name, runtime_variables)
        chat_model = self._model_for_timeout(timeout_seconds)
        schema = schema_for_prompt(prompt_name)
        if schema is None:
            raw_message = chat_model.invoke(prompt)
            content = _message_content(raw_message)
            if not content:
                raise RuntimeError("LangChain model returned empty message content")
            return self._build_result(
                raw_message=raw_message,
                content=content,
                attempts=1,
                structured_method=None,
            )

        try:
            return self._run_structured(
                chat_model=chat_model,
                prompt=prompt,
                schema=schema,
                method=self.structured_output_method,
                attempts=1,
            )
        except Exception as exc:
            fallback_method = self.structured_output_fallback_method
            if fallback_method is None or fallback_method == self.structured_output_method:
                raise
            return self._run_structured(
                chat_model=chat_model,
                prompt=prompt,
                schema=schema,
                method=fallback_method,
                attempts=2,
                fallback_reason=exc.__class__.__name__,
            )

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return self.run_prompt_result(prompt_name, variables).content
