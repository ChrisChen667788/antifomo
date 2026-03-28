from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.tasks import WorkTaskOut
from app.schemas.workbuddy import (
    WorkBuddyCallbackResultOut,
    WorkBuddyWebhookRequest,
    WorkBuddyWebhookResponse,
)
from app.services.task_runtime import create_and_execute_task
from app.services.user_context import ensure_demo_user
from app.services.workbuddy_adapter import (
    dispatch_workbuddy_callback,
    probe_official_gateway,
    verify_workbuddy_signature,
)


router = APIRouter(prefix="/api/workbuddy", tags=["workbuddy"])
settings = get_settings()


@router.get("/health")
def workbuddy_health() -> dict[str, object]:
    official_probe = probe_official_gateway(
        cli_command=settings.workbuddy_official_cli_command,
        gateway_url=settings.workbuddy_official_gateway_url,
        gateway_health_url=settings.workbuddy_official_gateway_health_url,
        bearer_token=settings.workbuddy_official_gateway_bearer_token,
        timeout_seconds=settings.workbuddy_official_probe_timeout_seconds,
    )
    requested_mode = str(settings.workbuddy_mode or "auto").strip().lower()
    if official_probe.gateway_reachable:
        integration_mode = "official_gateway_bridge"
        provider_label = "Tencent CodeBuddy official gateway bridge"
    elif official_probe.cli_authenticated:
        integration_mode = "official_cli_bridge"
        provider_label = "Tencent CodeBuddy official CLI bridge"
    else:
        integration_mode = "local_webhook_adapter"
        provider_label = "WorkBuddy-compatible local webhook adapter"
    return {
        "status": "ok",
        "signature_required": bool(str(settings.workbuddy_webhook_secret or "").strip()),
        "integration_mode": integration_mode,
        "official_tencent_connected": bool(official_probe.gateway_reachable or official_probe.cli_authenticated),
        "provider_label": provider_label,
        "requested_mode": requested_mode,
        "official_cli_detected": official_probe.cli_detected,
        "official_cli_version": official_probe.cli_version,
        "official_cli_authenticated": official_probe.cli_authenticated,
        "official_cli_auth_detail": official_probe.cli_auth_detail,
        "official_gateway_configured": official_probe.gateway_configured,
        "official_gateway_reachable": official_probe.gateway_reachable,
        "official_gateway_url": official_probe.gateway_url,
        "official_gateway_status_code": official_probe.gateway_status_code,
        "official_gateway_detail": official_probe.gateway_detail,
        "active_roles": [
            "session summary export",
            "reading list export",
            "todo draft export",
            "knowledge markdown export",
            "research report export",
            "focus assistant delegation",
        ],
    }


@router.post("/webhook", response_model=WorkBuddyWebhookResponse, status_code=status.HTTP_202_ACCEPTED)
async def workbuddy_webhook(
    payload: WorkBuddyWebhookRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WorkBuddyWebhookResponse:
    ensure_demo_user(db)

    raw_body = await request.body()
    signature = request.headers.get(settings.workbuddy_signature_header)
    timestamp = request.headers.get(settings.workbuddy_timestamp_header)
    verify_result = verify_workbuddy_signature(
        secret=settings.workbuddy_webhook_secret,
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
        max_age_seconds=settings.workbuddy_signature_ttl_seconds,
    )
    if not verify_result.ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid workbuddy signature: {verify_result.reason}",
        )

    if payload.event_type == "ping":
        return WorkBuddyWebhookResponse(
            accepted=True,
            event_type="ping",
            request_id=payload.request_id,
            message="pong",
            signature_check=verify_result.reason,
            task=None,
        )

    task = create_and_execute_task(
        db,
        user_id=settings.single_user_id,
        task_type=str(payload.task_type),
        session_id=payload.session_id,
        input_payload=payload.input_payload,
    )
    task_out = WorkTaskOut.model_validate(task)

    callback_out = WorkBuddyCallbackResultOut(attempted=False)
    requested_mode = str(settings.workbuddy_mode or "auto").strip().lower()
    default_callback_url = (
        str(settings.workbuddy_official_gateway_webhook_url or "").strip()
        if requested_mode in {"official", "auto"}
        else ""
    )
    callback_url = (
        str(payload.callback.url).strip()
        if payload.callback and payload.callback.url
        else default_callback_url or str(settings.workbuddy_default_callback_url or "").strip()
    )
    callback_headers = payload.callback.headers if payload.callback else {}
    if callback_url:
        event_name = "task.completed" if task.status == "done" else "task.failed"
        callback_payload = {
            "event_type": event_name,
            "source": "anti-fomo-demo",
            "request_id": payload.request_id,
            "task": task_out.model_dump(mode="json"),
        }
        dispatch_result = dispatch_workbuddy_callback(
            callback_url=callback_url,
            payload=callback_payload,
            headers=callback_headers,
            bearer_token=(
                settings.workbuddy_official_gateway_bearer_token
                if callback_url == default_callback_url and default_callback_url
                else settings.workbuddy_callback_bearer_token
            ),
            timeout_seconds=settings.workbuddy_callback_timeout_seconds,
        )
        callback_out = WorkBuddyCallbackResultOut(
            attempted=True,
            ok=dispatch_result.ok,
            status_code=dispatch_result.status_code,
            detail=dispatch_result.detail,
        )

    return WorkBuddyWebhookResponse(
        accepted=True,
        event_type="create_task",
        request_id=payload.request_id,
        message="task accepted",
        signature_check=verify_result.reason,
        task=task_out,
        callback=callback_out,
    )
