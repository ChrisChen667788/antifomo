from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi.testclient import TestClient

from app.main import app
from app.services.internal_skill_registry import (
    build_internal_skill_governance_snapshot,
    is_skill_allowed_in_default_generation,
    list_internal_skill_registry,
)


def _walk_keys(payload: Any) -> Iterable[str]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_keys(item)


def test_unreviewed_skills_do_not_enter_default_generation_chain() -> None:
    snapshot = build_internal_skill_governance_snapshot()
    default_chain_ids = set(snapshot["default_chain_skill_ids"])
    entries = list_internal_skill_registry()

    assert default_chain_ids
    assert snapshot["diagnostics"]["default_chain_blocking_enforced"] is True
    assert snapshot["diagnostics"]["unreviewed_default_chain_count"] == 0

    unreviewed_entries = [
        entry
        for entry in entries
        if entry["stage"] != "production" or entry["evaluation_status"] != "passed"
    ]
    assert unreviewed_entries
    assert all(entry["skill_id"] not in default_chain_ids for entry in unreviewed_entries)
    assert all(not is_skill_allowed_in_default_generation(entry["skill_id"]) for entry in unreviewed_entries)


def test_production_skills_have_regression_suites_and_version_history() -> None:
    production_entries = [
        entry for entry in list_internal_skill_registry() if entry["stage"] == "production"
    ]

    assert production_entries
    for entry in production_entries:
        assert entry["evaluation_status"] == "passed", entry["skill_id"]
        assert entry["default_generation_enabled"] is True, entry["skill_id"]
        assert entry["owner"], entry["skill_id"]
        assert entry["license"], entry["skill_id"]
        assert entry["rollback"], entry["skill_id"]
        assert entry["dependencies"], entry["skill_id"]
        assert entry["applicable_documents"], entry["skill_id"]
        assert entry["regression_suites"], entry["skill_id"]
        assert entry["version_history"], entry["skill_id"]
        assert all(suite["path"].startswith("backend/tests/") for suite in entry["regression_suites"])


def test_internal_skill_governance_endpoint_exposes_diagnostics_without_secret_values() -> None:
    with TestClient(app) as client:
        response = client.get("/api/system/internal-skills")

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["external_api_skills"] >= 1
    assert payload["summary"]["secret_required_skills"] >= 1
    assert payload["diagnostics"]["external_api_status_visible"] is True
    assert payload["diagnostics"]["secret_status_visible"] is True
    assert payload["diagnostics"]["data_egress_status_visible"] is True
    assert payload["diagnostics"]["secret_values_exposed"] is False
    assert "external_blocked" in payload["diagnostics"]["data_egress_modes"]
    assert payload["blocked_from_default_chain_skill_ids"]

    exposed_keys = set(_walk_keys(payload))
    assert "secret_value" not in exposed_keys
    assert "api_key" not in exposed_keys
    assert "token" not in exposed_keys
