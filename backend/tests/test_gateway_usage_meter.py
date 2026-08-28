from __future__ import annotations

from types import SimpleNamespace

from app.services import gateway_usage_meter


def test_gateway_usage_capture_deduplicates_credentials_and_never_returns_keys(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch(url: str, api_key: str, **_: object) -> dict[str, int]:
        calls.append(api_key)
        return {"total_used": 1200, "total_granted": 5000, "total_available": 3800}

    monkeypatch.setattr(gateway_usage_meter, "_fetch_usage", fake_fetch)
    settings = SimpleNamespace(
        gateway_usage_meter_enabled=True,
        gateway_usage_url="https://gateway.example/api/usage/token",
        gateway_usage_timeout_seconds=3,
        openai_verify_ssl=True,
        openai_api_key="shared-secret",
        openai_fallback_api_key=None,
        strategy_openai_api_key="shared-secret",
        strategy_openai_fallback_api_key=None,
    )

    result = gateway_usage_meter.capture_gateway_usage(settings)

    assert result["status"] == "ready"
    assert calls == ["shared-secret"]
    assert len(result["credentials"]) == 1
    assert "shared-secret" not in str(result)


def test_gateway_billing_calculates_report_level_cny_delta() -> None:
    before = {
        "credentials": {
            "credential-a": {"label": "generation_primary", "status": "ready", "total_used": 1000},
            "credential-b": {"label": "strategy_primary", "status": "ready", "total_used": 600},
        }
    }
    after = {
        "credentials": {
            "credential-a": {"label": "generation_primary", "status": "ready", "total_used": 151000},
            "credential-b": {"label": "strategy_primary", "status": "ready", "total_used": 50600},
        }
    }

    result = gateway_usage_meter.calculate_gateway_billing(
        before,
        after,
        quota_units_per_cny=500_000,
    )

    assert result["status"] == "measured"
    assert result["quota_units"] == 200_000
    assert result["estimated_cost_cny"] == 0.4
    assert result["currency"] == "CNY"
    assert result["includes_concurrent_usage"] is True
