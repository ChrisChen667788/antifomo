from __future__ import annotations

import hashlib
import json
import ssl
import time
from typing import Any
from urllib import request


def _credential_id(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def _fetch_usage(url: str, api_key: str, *, timeout_seconds: int, verify_ssl: bool) -> dict[str, int]:
    separator = "&" if "?" in url else "?"
    req = request.Request(
        f"{url}{separator}_={time.time_ns()}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Cache-Control": "no-cache",
            "User-Agent": "anti-fomo-cost-meter/1.0",
        },
        method="GET",
    )
    context = None if verify_ssl else ssl._create_unverified_context()
    with request.urlopen(req, timeout=max(2, min(int(timeout_seconds), 20)), context=context) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or "total_used" not in data:
        raise ValueError("gateway usage response has no total_used field")
    return {
        "total_used": int(data.get("total_used") or 0),
        "total_granted": int(data.get("total_granted") or 0),
        "total_available": int(data.get("total_available") or 0),
    }


def capture_gateway_usage(settings: Any) -> dict[str, Any]:
    url = str(getattr(settings, "gateway_usage_url", "") or "").strip()
    if not bool(getattr(settings, "gateway_usage_meter_enabled", False)) or not url:
        return {"status": "disabled", "credentials": {}}
    credentials: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for label, value in (
        ("generation_primary", getattr(settings, "openai_api_key", None)),
        ("generation_fallback", getattr(settings, "openai_fallback_api_key", None)),
        ("strategy_primary", getattr(settings, "strategy_openai_api_key", None)),
        ("strategy_fallback", getattr(settings, "strategy_openai_fallback_api_key", None)),
    ):
        api_key = str(value or "").strip()
        if not api_key or api_key in seen:
            continue
        seen.add(api_key)
        credential_id = _credential_id(api_key)
        try:
            usage = _fetch_usage(
                url,
                api_key,
                timeout_seconds=int(getattr(settings, "gateway_usage_timeout_seconds", 6)),
                verify_ssl=bool(getattr(settings, "openai_verify_ssl", True)),
            )
            credentials[credential_id] = {"label": label, "status": "ready", **usage}
        except Exception as exc:
            credentials[credential_id] = {
                "label": label,
                "status": "unavailable",
                "error": exc.__class__.__name__,
            }
    ready_count = sum(1 for row in credentials.values() if row.get("status") == "ready")
    return {
        "status": "ready" if ready_count == len(credentials) and ready_count else "partial" if ready_count else "unavailable",
        "captured_at": time.time(),
        "credentials": credentials,
    }


def calculate_gateway_billing(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    quota_units_per_cny: int,
) -> dict[str, Any]:
    before_rows = before.get("credentials") if isinstance(before, dict) else None
    after_rows = after.get("credentials") if isinstance(after, dict) else None
    if not isinstance(before_rows, dict) or not isinstance(after_rows, dict):
        return {"status": "unavailable", "pricing_source": "gateway_quota_delta"}
    deltas: list[dict[str, Any]] = []
    for credential_id, start in before_rows.items():
        end = after_rows.get(credential_id)
        if not isinstance(start, dict) or not isinstance(end, dict):
            continue
        if start.get("status") != "ready" or end.get("status") != "ready":
            continue
        delta = int(end.get("total_used") or 0) - int(start.get("total_used") or 0)
        if delta < 0:
            continue
        deltas.append({"route": start.get("label"), "quota_units": delta})
    if not deltas:
        return {"status": "unavailable", "pricing_source": "gateway_quota_delta"}
    total_units = sum(int(row["quota_units"]) for row in deltas)
    units_per_cny = max(1, int(quota_units_per_cny))
    return {
        "status": "measured" if total_units > 0 else "zero_delta",
        "currency": "CNY",
        "quota_units": total_units,
        "quota_units_per_cny": units_per_cny,
        "estimated_cost_cny": round(total_units / units_per_cny, 6),
        "pricing_source": "gateway_quota_delta",
        "includes_concurrent_usage": True,
        "routes": deltas,
    }
