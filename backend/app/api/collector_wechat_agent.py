from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.collector_ocr_routes import _run_ocr_preview_with_variants
from app.api.collector_ops_serializers import (
    _to_wechat_agent_batch_command_response,
    _to_wechat_agent_batch_status_response,
    _to_wechat_agent_command_response,
    _to_wechat_agent_config_response,
    _to_wechat_agent_dedup_summary_response,
    _to_wechat_agent_health_response,
    _to_wechat_agent_self_heal_response,
    _to_wechat_agent_status_response,
)
from app.schemas.collector import (
    WechatAgentBatchCommandResponse,
    WechatAgentBatchStatusResponse,
    WechatAgentCapturePreviewResponse,
    WechatAgentCommandResponse,
    WechatAgentConfigPatchRequest,
    WechatAgentConfigResponse,
    WechatAgentDedupSummaryResponse,
    WechatAgentHealthResponse,
    WechatAgentOCRPreviewResponse,
    WechatAgentSelfHealResponse,
    WechatAgentStatusResponse,
)
from app.services.language import normalize_output_language
from app.services.wechat_pc_agent_daemon import (
    capture_wechat_agent_preview,
    get_wechat_agent_health_report,
    read_wechat_agent_config,
    read_wechat_agent_batch_status,
    read_wechat_agent_status,
    reset_wechat_agent_dedup_state,
    run_wechat_agent_batch,
    run_wechat_agent_once,
    self_heal_wechat_agent,
    start_wechat_agent,
    stop_wechat_agent,
    update_wechat_agent_config,
)


router = APIRouter(prefix="/api/collector", tags=["collector"])

CapturePreviewFn = Callable[[], dict[str, Any]]
RunOcrPreviewWithVariantsFn = Callable[..., Any]


def get_wechat_agent_status_impl() -> WechatAgentStatusResponse:
    return _to_wechat_agent_status_response(read_wechat_agent_status())


def get_wechat_agent_config_impl() -> WechatAgentConfigResponse:
    return _to_wechat_agent_config_response(read_wechat_agent_config())


def update_wechat_agent_config_impl(payload: WechatAgentConfigPatchRequest) -> WechatAgentConfigResponse:
    config = update_wechat_agent_config(payload.model_dump(exclude_none=True))
    return _to_wechat_agent_config_response(config)


def get_wechat_agent_health_impl(stale_minutes: int | None = None) -> WechatAgentHealthResponse:
    report = get_wechat_agent_health_report(stale_minutes)
    return _to_wechat_agent_health_response(report)


def self_heal_wechat_agent_impl(force: bool = False) -> WechatAgentSelfHealResponse:
    result = self_heal_wechat_agent(force=bool(force))
    return _to_wechat_agent_self_heal_response(result)


def get_wechat_agent_preview_capture_impl(
    *,
    capture_preview_fn: CapturePreviewFn = capture_wechat_agent_preview,
) -> WechatAgentCapturePreviewResponse:
    try:
        payload = capture_preview_fn()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - platform/runtime path
        raise HTTPException(status_code=500, detail=f"capture preview failed: {exc}") from exc
    return WechatAgentCapturePreviewResponse.model_validate(payload)


def get_wechat_agent_preview_ocr_impl(
    *,
    output_language: str = "zh-CN",
    capture_preview_fn: CapturePreviewFn = capture_wechat_agent_preview,
    run_ocr_preview_with_variants_fn: RunOcrPreviewWithVariantsFn = _run_ocr_preview_with_variants,
) -> WechatAgentOCRPreviewResponse:
    resolved_language = normalize_output_language(output_language)
    try:
        capture_payload = capture_preview_fn()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - platform/runtime path
        raise HTTPException(status_code=500, detail=f"capture preview failed: {exc}") from exc

    image_base64_value = str(capture_payload.get("image_base64") or "")
    mime_type_value = str(capture_payload.get("mime_type") or "image/png")
    if not image_base64_value:
        raise HTTPException(status_code=500, detail="empty image data from capture preview")
    preview = run_ocr_preview_with_variants_fn(
        image_base64=image_base64_value,
        mime_type=mime_type_value,
        source_url=None,
        title_hint=None,
        output_language=resolved_language,
    )
    return WechatAgentOCRPreviewResponse(
        captured_at=capture_payload["captured_at"],
        provider=preview.provider,
        confidence=preview.confidence,
        text_length=preview.text_length,
        title=preview.title,
        body_preview=preview.body_preview,
        keywords=preview.keywords,
        quality_ok=preview.quality_ok,
        quality_reason=preview.quality_reason,
    )


def start_wechat_agent_impl() -> WechatAgentCommandResponse:
    try:
        result = start_wechat_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


def stop_wechat_agent_impl() -> WechatAgentCommandResponse:
    try:
        result = stop_wechat_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


def run_wechat_agent_once_impl(
    *,
    output_language: str = "zh-CN",
    max_items: int = 36,
    start_batch_index: int = 0,
    wait: bool = False,
) -> WechatAgentCommandResponse:
    safe_max_items = max(1, min(max_items, 200))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    try:
        result = run_wechat_agent_once(
            output_language=normalize_output_language(output_language),
            max_items=safe_max_items,
            start_batch_index=safe_start_batch_index,
            wait=bool(wait),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_command_response(result)


def get_wechat_agent_batch_status_impl() -> WechatAgentBatchStatusResponse:
    return _to_wechat_agent_batch_status_response(read_wechat_agent_batch_status())


def get_wechat_agent_dedup_summary_impl() -> WechatAgentDedupSummaryResponse:
    return _to_wechat_agent_dedup_summary_response()


def reset_wechat_agent_dedup_impl(clear_runs: bool = False) -> WechatAgentDedupSummaryResponse:
    try:
        summary = reset_wechat_agent_dedup_state(clear_runs=bool(clear_runs))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WechatAgentDedupSummaryResponse(
        processed_hashes=summary.processed_hashes,
        run_count=summary.run_count,
        last_run_started_at=summary.last_run_started_at,
        last_run_finished_at=summary.last_run_finished_at,
        last_run_submitted=summary.last_run_submitted,
        last_run_skipped_seen=summary.last_run_skipped_seen,
        last_run_failed=summary.last_run_failed,
        last_run_item_ids=summary.last_run_item_ids,
    )


def run_wechat_agent_batch_impl(
    *,
    output_language: str = "zh-CN",
    total_items: int = 50,
    segment_items: int = 10,
    start_batch_index: int = 0,
) -> WechatAgentBatchCommandResponse:
    safe_total_items = max(1, min(total_items, 200))
    safe_segment_items = max(1, min(segment_items, safe_total_items, 100))
    safe_start_batch_index = max(0, min(start_batch_index, 1_000))
    try:
        result = run_wechat_agent_batch(
            output_language=normalize_output_language(output_language),
            total_items=safe_total_items,
            segment_items=safe_segment_items,
            start_batch_index=safe_start_batch_index,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_wechat_agent_batch_command_response(result)


@router.get("/wechat-agent/status", response_model=WechatAgentStatusResponse)
def get_wechat_agent_status() -> WechatAgentStatusResponse:
    return get_wechat_agent_status_impl()


@router.get("/wechat-agent/config", response_model=WechatAgentConfigResponse)
def get_wechat_agent_config_api() -> WechatAgentConfigResponse:
    return get_wechat_agent_config_impl()


@router.put("/wechat-agent/config", response_model=WechatAgentConfigResponse)
def update_wechat_agent_config_api(
    payload: WechatAgentConfigPatchRequest,
) -> WechatAgentConfigResponse:
    return update_wechat_agent_config_impl(payload)


@router.get("/wechat-agent/health", response_model=WechatAgentHealthResponse)
def get_wechat_agent_health_api(stale_minutes: int | None = None) -> WechatAgentHealthResponse:
    return get_wechat_agent_health_impl(stale_minutes)


@router.post("/wechat-agent/self-heal", response_model=WechatAgentSelfHealResponse)
def self_heal_wechat_agent_api(force: bool = False) -> WechatAgentSelfHealResponse:
    return self_heal_wechat_agent_impl(force)


@router.get("/wechat-agent/preview-capture", response_model=WechatAgentCapturePreviewResponse)
def get_wechat_agent_preview_capture_api() -> WechatAgentCapturePreviewResponse:
    return get_wechat_agent_preview_capture_impl()


@router.get("/wechat-agent/preview-ocr", response_model=WechatAgentOCRPreviewResponse)
def get_wechat_agent_preview_ocr_api(output_language: str = "zh-CN") -> WechatAgentOCRPreviewResponse:
    return get_wechat_agent_preview_ocr_impl(output_language=output_language)


@router.post("/wechat-agent/start", response_model=WechatAgentCommandResponse)
def start_wechat_agent_api() -> WechatAgentCommandResponse:
    return start_wechat_agent_impl()


@router.post("/wechat-agent/stop", response_model=WechatAgentCommandResponse)
def stop_wechat_agent_api() -> WechatAgentCommandResponse:
    return stop_wechat_agent_impl()


@router.post("/wechat-agent/run-once", response_model=WechatAgentCommandResponse)
def run_wechat_agent_once_api(
    output_language: str = "zh-CN",
    max_items: int = 36,
    start_batch_index: int = 0,
    wait: bool = False,
) -> WechatAgentCommandResponse:
    return run_wechat_agent_once_impl(
        output_language=output_language,
        max_items=max_items,
        start_batch_index=start_batch_index,
        wait=wait,
    )


@router.get("/wechat-agent/batch-status", response_model=WechatAgentBatchStatusResponse)
def get_wechat_agent_batch_status_api() -> WechatAgentBatchStatusResponse:
    return get_wechat_agent_batch_status_impl()


@router.get("/wechat-agent/dedup-summary", response_model=WechatAgentDedupSummaryResponse)
def get_wechat_agent_dedup_summary_api() -> WechatAgentDedupSummaryResponse:
    return get_wechat_agent_dedup_summary_impl()


@router.post("/wechat-agent/reset-dedup", response_model=WechatAgentDedupSummaryResponse)
def reset_wechat_agent_dedup_api(clear_runs: bool = False) -> WechatAgentDedupSummaryResponse:
    return reset_wechat_agent_dedup_impl(clear_runs)


@router.post("/wechat-agent/run-batch", response_model=WechatAgentBatchCommandResponse)
def run_wechat_agent_batch_api(
    output_language: str = "zh-CN",
    total_items: int = 50,
    segment_items: int = 10,
    start_batch_index: int = 0,
) -> WechatAgentBatchCommandResponse:
    return run_wechat_agent_batch_impl(
        output_language=output_language,
        total_items=total_items,
        segment_items=segment_items,
        start_batch_index=start_batch_index,
    )
