from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.model_control_plane_service import (
    build_model_control_plane_snapshot,
    scan_supported_models,
    upgrade_to_strongest_models,
)


CATALOG = [
    {"id": "gpt-5.4", "owned_by": "openai", "created": 10},
    {"id": "gpt-5.5", "owned_by": "openai", "created": 20},
    {"id": "gpt-5.5-vision", "owned_by": "openai", "created": 21},
    {"id": "claude-sonnet-4-7", "owned_by": "anthropic", "created": 18},
    {"id": "claude-opus-4-7", "owned_by": "anthropic", "created": 19},
    {"id": "gpt-5.3-codex", "owned_by": "openai", "created": 17},
    {"id": "text-embedding-3-large", "owned_by": "openai", "created": 5},
]


def _settings(**overrides) -> Settings:
    values = {
        "llm_provider": "openai",
        "openai_api_key": "test-key",
        "openai_base_url": "https://models.example/v1",
        "openai_model": "gpt-5.4",
        "openai_vision_model": "gpt-5.4",
        "strategy_llm_provider": "openai",
        "strategy_openai_api_key": "test-key",
        "strategy_openai_base_url": "https://models.example/v1",
        "strategy_openai_model": "claude-sonnet-4-7",
        "strategy_model_qualification_required": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_control_plane_exposes_real_module_routes() -> None:
    snapshot = build_model_control_plane_snapshot(_settings())

    bindings = {row["key"]: row for row in snapshot["modules"]}
    assert bindings["research_generation"]["model"] == "gpt-5.4"
    assert bindings["research_strategy"]["model"] == "claude-sonnet-4-7"
    assert bindings["session_summary"]["route_key"] == "generation"
    assert bindings["focus_assistant"]["provider"] == "auto"
    assert bindings["wechat_parser"]["model"] == "claude-sonnet-4-7"
    assert bindings["wechat_parser"]["route_key"] == "strategy"
    assert bindings["wechat_parser"]["upgrade_managed"] is True
    assert bindings["decision_semantic_search"]["model"] == "BAAI/bge-m3"
    assert bindings["decision_semantic_search"]["route_key"] == "decision_embedding"
    assert bindings["decision_document_parser"]["route_key"] == "deterministic"


def test_scan_deduplicates_catalog_calls_and_recommends_by_role() -> None:
    calls: list[str] = []

    def fetcher(route: dict) -> list[dict]:
        calls.append(route["route_key"])
        return CATALOG

    result = scan_supported_models(_settings(), fetcher=fetcher)

    assert result["status"] == "ready"
    assert result["total_discovered"] == len(CATALOG)
    assert calls == ["generation"]
    recommendations = {row["role"]: row["model"] for row in result["recommendations"]}
    assert recommendations == {
        "generation": "gpt-5.5",
        "strategy": "claude-opus-4-7",
        "vision": "gpt-5.5-vision",
    }
    excluded = {row["id"]: row for row in result["models"]}
    assert excluded["gpt-5.3-codex"]["excluded"] is True
    assert excluded["text-embedding-3-large"]["excluded"] is True


def test_scan_blocks_bulk_upgrade_when_a_route_fails() -> None:
    def fetcher(route: dict) -> list[dict]:
        if route["route_key"] == "strategy":
            raise RuntimeError("provider unavailable with secret details")
        return CATALOG

    settings = _settings(strategy_openai_api_key="different-key")
    result = scan_supported_models(settings, fetcher=fetcher)

    assert result["status"] == "partial"
    assert next(row for row in result["routes"] if row["route_key"] == "strategy")["error_code"] == "scan_failed"
    assert "secret details" not in str(result)


def test_scan_retries_with_fallback_credentials_when_primary_is_unavailable() -> None:
    calls: list[str] = []

    def fetcher(route: dict) -> list[dict]:
        calls.append(route["api_key"])
        if route["api_key"] == "test-key":
            raise RuntimeError("primary quota exhausted")
        return CATALOG

    settings = _settings(
        openai_fallback_api_key="fallback-key",
        strategy_openai_fallback_api_key="fallback-key",
    )
    result = scan_supported_models(settings, fetcher=fetcher)

    assert result["status"] == "ready"
    assert calls == ["test-key", "fallback-key"]
    assert all("备用密钥" in route["message"] for route in result["routes"])
    assert "quota exhausted" not in str(result)


def test_scan_requires_a_vision_capable_recommendation_for_auto_ocr() -> None:
    catalog = [
        {"id": "qwen-3-max", "owned_by": "qwen", "created": 20},
        {"id": "deepseek-r2", "owned_by": "deepseek", "created": 21},
    ]

    result = scan_supported_models(_settings(), fetcher=lambda _route: catalog)

    assert result["status"] == "partial"
    assert {row["role"] for row in result["recommendations"]} == {"generation", "strategy"}


def test_upgrade_persists_models_and_refreshes_runtime(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_API_KEY=keep-this-secret\nOPENAI_MODEL=gpt-5.4\nOPENAI_VISION_MODEL=gpt-5.4\n"
        "STRATEGY_OPENAI_MODEL=claude-sonnet-4-7\nCUSTOM_FLAG=1\n",
        encoding="utf-8",
    )
    refreshes: list[bool] = []
    settings = _settings()

    result = upgrade_to_strongest_models(
        settings,
        env_path=env_path,
        fetcher=lambda _route: CATALOG,
        runtime_refresh=lambda: refreshes.append(True),
    )

    assert result["status"] == "applied"
    assert set(result["changed_fields"]) == {
        "openai_model",
        "openai_vision_model",
        "strategy_openai_model",
    }
    assert settings.openai_model == "gpt-5.5"
    assert settings.openai_vision_model == "gpt-5.5-vision"
    assert settings.strategy_openai_model == "claude-opus-4-7"
    assert refreshes == [True]
    persisted = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=keep-this-secret" in persisted
    assert "OPENAI_MODEL=gpt-5.5\n" in persisted
    assert "OPENAI_VISION_MODEL=gpt-5.5-vision\n" in persisted
    assert "STRATEGY_OPENAI_MODEL=claude-opus-4-7\n" in persisted
    assert "CUSTOM_FLAG=1" in persisted


def test_upgrade_is_atomic_when_scan_is_blocked(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    original = "OPENAI_MODEL=gpt-5.4\n"
    env_path.write_text(original, encoding="utf-8")
    settings = _settings(strategy_openai_api_key="different-key")

    result = upgrade_to_strongest_models(
        settings,
        env_path=env_path,
        fetcher=lambda _route: (_ for _ in ()).throw(RuntimeError("offline")),
        runtime_refresh=lambda: None,
    )

    assert result["status"] == "blocked"
    assert env_path.read_text(encoding="utf-8") == original
    assert settings.openai_model == "gpt-5.4"


def test_upgrade_keeps_vision_model_when_ocr_is_local(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENAI_MODEL=gpt-5.4\nOPENAI_VISION_MODEL=local-only-placeholder\n"
        "STRATEGY_OPENAI_MODEL=claude-sonnet-4-7\n",
        encoding="utf-8",
    )
    settings = _settings(ocr_provider="local", openai_vision_model="local-only-placeholder")

    result = upgrade_to_strongest_models(
        settings,
        env_path=env_path,
        fetcher=lambda _route: CATALOG,
        runtime_refresh=lambda: None,
    )

    assert result["status"] == "applied"
    assert "openai_vision_model" not in result["changed_fields"]
    assert settings.openai_vision_model == "local-only-placeholder"
    assert "OPENAI_VISION_MODEL=local-only-placeholder" in env_path.read_text(encoding="utf-8")
