from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Anti-fomo API"
    app_env: str = "dev"
    database_url: str = "sqlite:///./anti_fomo_demo.db"
    single_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    llm_provider: str = "mock"
    llm_fallback_to_mock: bool = True
    ocr_provider: str = "auto"  # auto / local / openai / mock
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "claude-opus-4-6"
    openai_vision_model: str | None = "claude-opus-4-6"
    openai_temperature: float = 0.2
    openai_timeout_seconds: int = 120
    strategy_openai_api_key: str | None = None
    strategy_openai_base_url: str = "https://api.openai.com/v1"
    strategy_openai_model: str = "gpt-5.4"
    strategy_openai_temperature: float = 0.1
    strategy_openai_timeout_seconds: int = 90
    item_llm_timeout_seconds: int = 6
    interpret_llm_timeout_seconds: int = 8
    research_llm_timeout_seconds: int = 180
    openai_organization: str | None = None
    openai_project: str | None = None
    openai_verify_ssl: bool = True
    openai_ca_bundle: str | None = None
    url_fetch_timeout_seconds: int = 20
    research_search_timeout_seconds: int = 15
    research_search_query_limit: int = 12
    research_max_search_results: int = 12
    research_max_sources: int = 14
    research_source_excerpt_chars: int = 900
    wechat_agent_auto_start: bool = False
    pending_item_recovery_enabled: bool = True
    pending_item_recovery_interval_seconds: int = 8
    pending_item_grace_seconds: int = 10
    processing_stale_seconds: int = 90
    pending_item_recovery_batch_size: int = 12
    pending_item_max_attempts: int = 4
    workbuddy_webhook_secret: str | None = None
    workbuddy_mode: str = "auto"  # auto / local / official
    workbuddy_signature_header: str = "x-workbuddy-signature"
    workbuddy_timestamp_header: str = "x-workbuddy-timestamp"
    workbuddy_signature_ttl_seconds: int = 300
    workbuddy_default_callback_url: str | None = None
    workbuddy_callback_bearer_token: str | None = None
    workbuddy_callback_timeout_seconds: int = 12
    workbuddy_official_cli_command: str = "codebuddy"
    workbuddy_official_gateway_url: str | None = None
    workbuddy_official_gateway_health_url: str | None = None
    workbuddy_official_gateway_webhook_url: str | None = None
    workbuddy_official_gateway_bearer_token: str | None = None
    workbuddy_official_probe_timeout_seconds: int = 6
    workbuddy_official_cli_timeout_seconds: int = 90

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
