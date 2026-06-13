from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.core.config import get_settings
from app.services.llm_parser import (
    parse_insight_response,
    parse_research_report_response,
    parse_research_strategy_refine_response,
    parse_research_strategy_scope_response,
    parse_score_response,
    parse_session_summary_response,
    parse_summarize_response,
    parse_tags_response,
)
from app.services.llm_service import build_llm_service, run_llm_prompt_result
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
    model: str = ""
    usage: dict[str, int | str] = Field(default_factory=dict)
    estimated_cost_usd: float | None = None
    ok: bool
    error: str | None = None


@router.get("/llm/config")
def get_llm_config() -> dict:
    return {
        "llm_provider": settings.llm_provider,
        "llm_fallback_to_mock": settings.llm_fallback_to_mock,
        "llm_max_retries": settings.llm_max_retries,
        "langchain_structured_output_method": settings.langchain_structured_output_method,
        "langchain_structured_output_fallback_method": settings.langchain_structured_output_fallback_method,
        "ocr_provider": settings.ocr_provider,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "openai_vision_model": settings.openai_vision_model,
        "openai_temperature": settings.openai_temperature,
        "openai_timeout_seconds": settings.openai_timeout_seconds,
        "openai_api_key_configured": bool(settings.openai_api_key),
        "openai_pricing_configured": (
            settings.openai_input_cost_per_million is not None
            and settings.openai_output_cost_per_million is not None
        ),
        "openai_pricing_per_million_usd": {
            "input": settings.openai_input_cost_per_million,
            "cached_input": settings.openai_cached_input_cost_per_million,
            "output": settings.openai_output_cost_per_million,
        },
        "strategy_llm_provider": settings.strategy_llm_provider,
        "strategy_openai_base_url": settings.strategy_openai_base_url,
        "strategy_openai_model": settings.strategy_openai_model,
        "strategy_openai_timeout_seconds": settings.strategy_openai_timeout_seconds,
        "strategy_openai_api_key_configured": bool(settings.strategy_openai_api_key),
        "strategy_openai_pricing_configured": (
            settings.strategy_openai_input_cost_per_million is not None
            and settings.strategy_openai_output_cost_per_million is not None
        ),
        "strategy_openai_pricing_per_million_usd": {
            "input": settings.strategy_openai_input_cost_per_million,
            "cached_input": settings.strategy_openai_cached_input_cost_per_million,
            "output": settings.strategy_openai_output_cost_per_million,
        },
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
    if prompt_name == "interpret.txt":
        return parse_insight_response(raw).model_dump()
    if prompt_name == "research_report.txt":
        return parse_research_report_response(raw).model_dump()
    if prompt_name in {"research_report_outline.txt", "research_strategy_refine.txt"}:
        return parse_research_strategy_refine_response(raw).model_dump()
    if prompt_name == "research_strategy_scope.txt":
        return parse_research_strategy_scope_response(raw).model_dump()
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
    service = build_llm_service(settings=settings)
    if service is None:
        raise RuntimeError("LLM provider route returned no service")
    try:
        # Validate template is renderable before remote call.
        _ = render_prompt(prompt_name, merged_variables)
        result = run_llm_prompt_result(service, prompt_name, merged_variables)
        fallback_used = result.status == "fallback" or result.provider != requested
        missing_key = requested != "mock" and not settings.openai_api_key
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used=result.provider,
            fallback_used=fallback_used,
            raw_preview=result.content[:800],
            parsed_preview=_parse_by_prompt_name(prompt_name, result.content),
            model=result.model,
            usage={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "total_tokens": result.usage.total_tokens,
                "cached_input_tokens": result.usage.cached_input_tokens,
                "source": result.usage.source,
            },
            estimated_cost_usd=result.estimated_cost_usd,
            ok=not missing_key,
            error="OPENAI_API_KEY is empty, fallback to mock" if missing_key else None,
        )
    except Exception as exc:
        return LLMDryRunResponse(
            provider_requested=requested,
            provider_used=requested,
            fallback_used=False,
            raw_preview="",
            parsed_preview={},
            ok=False,
            error=str(exc),
        )
