from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.core.config import get_settings
from app.services.llm_parser import (
    parse_score_response,
    parse_session_summary_response,
    parse_summarize_response,
    parse_tags_response,
)
from app.services.llm_service import MockLLMService, OpenAILLMService
from app.services.prompt_loader import render_prompt


router = APIRouter(prefix="/api/system", tags=["system"])
settings = get_settings()


class LLMDryRunRequest(BaseModel):
    prompt_name: str = Field(default="summarize.txt")
    variables: dict[str, str] = Field(default_factory=dict)


class LLMDryRunResponse(BaseModel):
    provider_requested: str
    provider_used: str
    fallback_used: bool
    raw_preview: str
    parsed_preview: dict
    ok: bool
    error: str | None = None


@router.get("/llm/config")
def get_llm_config() -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "llm_fallback_to_mock": settings.llm_fallback_to_mock,
        "ocr_provider": settings.ocr_provider,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "openai_vision_model": settings.openai_vision_model,
        "openai_temperature": settings.openai_temperature,
        "openai_timeout_seconds": settings.openai_timeout_seconds,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "strategy_openai_base_url": settings.strategy_openai_base_url,
        "strategy_openai_model": settings.strategy_openai_model,
        "strategy_openai_timeout_seconds": settings.strategy_openai_timeout_seconds,
        "strategy_openai_api_key_configured": bool(settings.strategy_openai_api_key),
    }


def _parse_by_prompt_name(prompt_name: str, raw: str) -> dict:
    if prompt_name == "summarize.txt":
        return parse_summarize_response(raw).model_dump()
    if prompt_name == "tags.txt":
        return parse_tags_response(raw).model_dump()
    if prompt_name == "score.txt":
        return parse_score_response(raw).model_dump()
    if prompt_name == "session_summary.txt":
        return parse_session_summary_response(raw).model_dump()
    return {}


@router.post("/llm/dry-run", response_model=LLMDryRunResponse)
def llm_dry_run(payload: LLMDryRunRequest) -> LLMDryRunResponse:
    prompt_name = payload.prompt_name
    variables = payload.variables

    # Fill minimal defaults to make dry-run one-click usable.
    defaults = {
        "title": "AI Agent 浏览器进入加速期",
        "source_domain": "36kr.com",
        "clean_content": "多家厂商近期发布 Agent Browser，关注点集中在自动执行、隐私保护与工作流集成。",
        "short_summary": "Agent Browser 赛道升温，能力焦点转向执行和隐私。",
        "long_summary": "文章讨论了 Agent Browser 赛道升温与竞争点变化，并分析对知识工作者效率的影响。",
        "goal_text": "整理 AI 行业求职材料",
        "session_items_summary_list": "- AI 求职趋势 | deep_read | 岗位结构变化与技能要求更新",
        "output_language": "zh-CN",
        "output_language_name": "简体中文 (zh-CN)",
    }
    merged_variables = {**defaults, **variables}

    requested = settings.llm_provider
    mock = MockLLMService()

    if requested != "openai":
        raw = mock.run_prompt(prompt_name, merged_variables)
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used="mock",
            fallback_used=False,
            raw_preview=raw[:800],
            parsed_preview=_parse_by_prompt_name(prompt_name, raw),
            ok=True,
        )

    if not settings.openai_api_key:
        raw = mock.run_prompt(prompt_name, merged_variables)
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used="mock",
            fallback_used=True,
            raw_preview=raw[:800],
            parsed_preview=_parse_by_prompt_name(prompt_name, raw),
            ok=False,
            error="OPENAI_API_KEY is empty, fallback to mock",
        )

    openai = OpenAILLMService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        timeout_seconds=settings.openai_timeout_seconds,
        organization=settings.openai_organization,
        project=settings.openai_project,
    )

    try:
        # Validate template is renderable before remote call.
        _ = render_prompt(prompt_name, merged_variables)
        raw = openai.run_prompt(prompt_name, merged_variables)
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used="openai",
            fallback_used=False,
            raw_preview=raw[:800],
            parsed_preview=_parse_by_prompt_name(prompt_name, raw),
            ok=True,
        )
    except Exception as exc:
        if not settings.llm_fallback_to_mock:
            return LLMDryRunResponse(
                provider_requested=requested,
                provider_used="openai",
                fallback_used=False,
                raw_preview="",
                parsed_preview={},
                ok=False,
                error=str(exc),
            )

        raw = mock.run_prompt(prompt_name, merged_variables)
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used="mock",
            fallback_used=True,
            raw_preview=raw[:800],
            parsed_preview=_parse_by_prompt_name(prompt_name, raw),
            ok=False,
            error=f"OpenAI failed: {exc}",
        )
