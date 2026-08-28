from __future__ import annotations

import json
import logging
import ssl
import time
from urllib import error, request

from app.services.llm_runtime import LLMRunResult, LLMUsage, ModelPricing, estimated_usage
from app.services.prompt_loader import render_prompt

_QUOTA_ERROR_TOKENS = (
    "insufficient_quota",
    "insufficient balance",
    "余额不足",
    "额度已用尽",
    "quota exceeded",
    "billing",
    "exceeded your current quota",
    "account has been deactivated",
    "plan has been exhausted",
)

logger = logging.getLogger("anti_fomo.llm")


class _QuotaExhaustedError(RuntimeError):
    """Internal signal used to retry once with the configured fallback key."""


class OpenAILLMService:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        timeout_seconds: int,
        organization: str | None = None,
        project: str | None = None,
        verify_ssl: bool = True,
        ca_bundle: str | None = None,
        fallback_api_key: str | None = None,
        pricing: ModelPricing | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.organization = organization
        self.project = project
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle
        self.fallback_api_key = fallback_api_key
        self.pricing = pricing or ModelPricing()
        self._using_fallback = False

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not self.verify_ssl:
            return ssl._create_unverified_context()

        cafile = self.ca_bundle
        if not cafile:
            try:
                import certifi

                cafile = certifi.where()
            except Exception:
                cafile = None

        if cafile:
            return ssl.create_default_context(cafile=cafile)
        return None

    @staticmethod
    def _is_quota_error(status_code: int, details: str) -> bool:
        if status_code == 402:
            return True
        lowered = details.lower()
        return any(token in lowered for token in _QUOTA_ERROR_TOKENS)

    def _active_api_key(self) -> str:
        if self._using_fallback and self.fallback_api_key:
            return self.fallback_api_key
        return self.api_key

    def _make_request(
        self,
        prompt: str,
        timeout_seconds: int,
        ssl_context: ssl.SSLContext | None,
        max_attempts: int,
        *,
        stream: bool = False,
        max_output_tokens: int | None = None,
    ) -> tuple[str, int]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        if stream:
            payload["stream"] = True
        if max_output_tokens is not None:
            payload["max_tokens"] = max(1, int(max_output_tokens))
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._active_api_key()}",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if self.project:
            headers["OpenAI-Project"] = self.project

        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        body = ""
        last_error: Exception | None = None
        deadline = time.monotonic() + max(1, timeout_seconds)
        for attempt in range(1, max_attempts + 1):
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                last_error = RuntimeError(f"OpenAI request exceeded total timeout of {timeout_seconds}s")
                break
            try:
                with request.urlopen(req, timeout=max(0.1, remaining_seconds), context=ssl_context) as resp:
                    if stream:
                        body = self._consume_stream_response(resp, deadline=deadline)
                    else:
                        body = resp.read().decode("utf-8", errors="ignore")
                last_error = None
                break
            except error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                if self._is_quota_error(exc.code, details):
                    raise _QuotaExhaustedError(details) from exc
                last_error = RuntimeError(f"OpenAI HTTP {exc.code}: {details}")
                should_retry = exc.code >= 500 and attempt < max_attempts
                if not should_retry:
                    raise last_error from exc
            except _QuotaExhaustedError:
                raise
            except Exception as exc:
                last_error = RuntimeError(f"OpenAI request failed: {exc}")
                message = str(exc).lower()
                should_retry = attempt < max_attempts and any(
                    token in message
                    for token in ("timed out", "timeout", "temporarily unavailable", "connection reset", "remote end closed")
                )
                if not should_retry:
                    raise last_error from exc
            retry_delay = min(2.0, 0.8 * attempt, max(0.0, deadline - time.monotonic()))
            if retry_delay <= 0:
                break
            time.sleep(retry_delay)
        if last_error is not None and not body:
            raise last_error
        return body, attempt

    @staticmethod
    def _stream_delta_text(delta: object) -> str:
        if not isinstance(delta, dict):
            return ""
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text") or block.get("content")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)

    def _consume_stream_response(self, response: object, *, deadline: float) -> str:
        content_parts: list[str] = []
        response_id = ""
        resolved_model = self.model
        finish_reason = ""
        usage: dict[str, object] = {}

        for raw_line in response:  # type: ignore[operator]
            if time.monotonic() > deadline:
                raise TimeoutError("OpenAI streaming response exceeded total timeout")
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line or line.startswith(":"):
                continue
            data = line[5:].strip() if line.startswith("data:") else line
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if not isinstance(chunk, dict):
                continue
            if isinstance(chunk.get("error"), dict):
                message = str(chunk["error"].get("message") or "OpenAI streaming response failed")
                raise RuntimeError(message)
            response_id = str(chunk.get("id") or response_id)
            resolved_model = str(chunk.get("model") or resolved_model)
            if isinstance(chunk.get("usage"), dict):
                usage = chunk["usage"]
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                continue
            choice = choices[0]
            finish_reason = str(choice.get("finish_reason") or finish_reason)
            text = self._stream_delta_text(choice.get("delta"))
            if not text and isinstance(choice.get("message"), dict):
                text = self._stream_delta_text(choice["message"])
            if text:
                content_parts.append(text)

        return json.dumps(
            {
                "id": response_id,
                "model": resolved_model,
                "choices": [
                    {
                        "message": {"content": "".join(content_parts)},
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": usage,
            },
            ensure_ascii=False,
        )

    def run_prompt_result(self, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
        runtime_variables = dict(variables)
        timeout_override = runtime_variables.pop("__timeout_seconds", None)
        stream_response = str(runtime_variables.pop("__stream_response", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        max_output_tokens_override = runtime_variables.pop("__max_output_tokens", None)
        prompt = render_prompt(prompt_name, runtime_variables)

        ssl_context = self._build_ssl_context()
        timeout_seconds = self.timeout_seconds
        if timeout_override is not None:
            try:
                timeout_seconds = max(1, int(timeout_override))
            except Exception:
                timeout_seconds = self.timeout_seconds
        max_output_tokens: int | None = None
        if max_output_tokens_override is not None:
            try:
                max_output_tokens = max(1, int(max_output_tokens_override))
            except Exception:
                max_output_tokens = None
        max_attempts = 2 if prompt_name == "research_report.txt" else 1

        try:
            body, attempts = self._make_request(
                prompt,
                timeout_seconds,
                ssl_context,
                max_attempts,
                stream=stream_response,
                max_output_tokens=max_output_tokens,
            )
        except _QuotaExhaustedError:
            if not self.fallback_api_key or self._using_fallback:
                raise RuntimeError("API quota exhausted and no fallback key available")
            logger.warning(
                "Quota exhausted on primary key, switching to fallback key for model=%s",
                self.model,
            )
            self._using_fallback = True
            body, fallback_attempts = self._make_request(
                prompt,
                timeout_seconds,
                ssl_context,
                max_attempts,
                stream=stream_response,
                max_output_tokens=max_output_tokens,
            )
            attempts = max_attempts + fallback_attempts

        try:
            response_json = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned non-JSON response") from exc

        content = extract_openai_message_content(response_json)
        if not content:
            raise RuntimeError("OpenAI returned empty message content")
        usage_payload = response_json.get("usage")
        if not isinstance(usage_payload, dict):
            usage_payload = {}
        input_details = usage_payload.get("prompt_tokens_details")
        if not isinstance(input_details, dict):
            input_details = {}
        input_tokens = int(usage_payload.get("prompt_tokens") or 0)
        output_tokens = int(usage_payload.get("completion_tokens") or 0)
        usage = (
            LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=int(usage_payload.get("total_tokens") or input_tokens + output_tokens),
                cached_input_tokens=int(input_details.get("cached_tokens") or 0),
                source="provider",
            )
            if usage_payload
            else estimated_usage(prompt, content)
        )
        choices = response_json.get("choices")
        first_choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        return LLMRunResult(
            content=content,
            provider=self.provider,
            model=str(response_json.get("model") or self.model),
            usage=usage,
            estimated_cost_usd=self.pricing.estimate_cost_usd(usage),
            attempts=attempts,
            response_id=str(response_json.get("id") or ""),
            finish_reason=str(first_choice.get("finish_reason") or ""),
            metadata={
                "fallback_api_key_used": self._using_fallback,
                "streamed": stream_response,
                "max_output_tokens": max_output_tokens or 0,
            },
        )

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return self.run_prompt_result(prompt_name, variables).content

def extract_openai_message_content(response_json: dict) -> str:
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_chunks: list[str] = []
        for chunk in content:
            if not isinstance(chunk, dict):
                continue
            text = chunk.get("text")
            if isinstance(text, str):
                text_chunks.append(text)
        return "\n".join(text_chunks).strip()
    return ""
