from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _normalize_sqlite_database_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    if raw in {"sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
        return raw
    for prefix in ("sqlite:///", "sqlite+pysqlite:///"):
        if not raw.startswith(prefix):
            continue
        relative_path = raw[len(prefix):]
        if relative_path.startswith("/"):
            return raw
        resolved = (BACKEND_DIR / relative_path.lstrip("./")).resolve()
        return f"{prefix}{resolved}"
    return raw


class Settings(BaseSettings):
    app_name: str = "Anti-fomo API"
    app_env: str = "dev"
    database_url: str = "sqlite:///./anti_fomo_demo.db"
    single_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    llm_provider: str = "mock"
    llm_fallback_to_mock: bool = True
    research_llm_fallback_to_mock: bool = False
    llm_max_retries: int = 1
    langchain_structured_output_method: str = "json_schema"
    langchain_structured_output_fallback_method: str | None = "json_mode"
    ocr_provider: str = "auto"  # auto / local / openai / mock
    openai_api_key: str | None = None
    openai_fallback_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"
    openai_vision_model: str | None = "gpt-5.5"
    openai_temperature: float = 0.2
    openai_timeout_seconds: int = 120
    openai_input_cost_per_million: float | None = None
    openai_cached_input_cost_per_million: float | None = None
    openai_output_cost_per_million: float | None = None
    strategy_llm_provider: str = "openai"
    strategy_openai_api_key: str | None = None
    strategy_openai_fallback_api_key: str | None = None
    strategy_openai_base_url: str = "https://api.openai.com/v1"
    strategy_openai_model: str = "claude-opus-4-7"
    strategy_openai_temperature: float = 0.1
    strategy_openai_timeout_seconds: int = 90
    strategy_llm_max_retries: int = 1
    strategy_model_qualification_required: bool = True
    strategy_model_qualification_max_age_days: int = 30
    strategy_openai_input_cost_per_million: float | None = None
    strategy_openai_cached_input_cost_per_million: float | None = None
    strategy_openai_output_cost_per_million: float | None = None
    item_llm_timeout_seconds: int = 6
    wechat_favorites_llm_role: str = "strategy"
    wechat_favorites_llm_timeout_seconds: int = 45
    ocr_item_llm_timeout_seconds: int = 3
    ocr_openai_timeout_seconds: int = 8
    interpret_llm_timeout_seconds: int = 8
    research_llm_timeout_seconds: int = 300
    research_llm_max_output_tokens: int = 7000
    openai_organization: str | None = None
    openai_project: str | None = None
    openai_verify_ssl: bool = True
    openai_ca_bundle: str | None = None
    url_fetch_timeout_seconds: int = 20
    browser_extractor_enabled: bool = True
    browser_extractor_timeout_seconds: int = 28
    browser_extractor_chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser_extractor_user_data_dir: str | None = None
    browser_extractor_profile_dir: str | None = None
    browser_extractor_headless: bool = True
    research_search_timeout_seconds: int = 15
    research_search_query_limit: int = 12
    research_max_search_results: int = 12
    research_max_sources: int = 14
    research_source_excerpt_chars: int = 900
    research_snapshot_recovery_enabled: bool = True
    research_snapshot_recovery_max_age_hours: int = 48
    research_cross_encoder_rerank_enabled: bool = False
    research_cross_encoder_backend: str = "auto"  # auto / sentence_transformers / local
    research_cross_encoder_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    research_cross_encoder_top_k: int = 20
    research_cross_encoder_cache_dir: str | None = None
    research_cross_encoder_device: str = "auto"
    decision_embedding_enabled: bool = True
    decision_embedding_provider: str = "sentence_transformers"
    decision_embedding_model: str = "BAAI/bge-m3"
    decision_embedding_batch_size: int = 16
    decision_embedding_cache_dir: str | None = None
    decision_embedding_xet_cache_dir: str | None = None
    decision_embedding_disable_symlinks: bool = False
    decision_embedding_device: str = "auto"
    decision_docling_enabled: bool = False
    decision_skill_signing_key: str | None = None
    decision_connector_allowed_domains: str = ""
    research_quality_expansion_enabled: bool = True
    research_quality_expansion_min_score: int = 82
    research_quality_expansion_max_rounds: int = 2
    research_quality_expansion_query_limit: int = 8
    research_workflow_engine: str = "langgraph"
    research_job_worker_enabled: bool = True
    research_job_worker_poll_seconds: float = 1.0
    research_job_lease_seconds: int = 1800
    research_job_recover_running_on_startup: bool = True
    research_job_recovery_max_age_hours: int = 24
    gateway_usage_meter_enabled: bool = False
    gateway_usage_url: str | None = None
    gateway_quota_units_per_cny: int = 500_000
    gateway_usage_timeout_seconds: int = 6
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
    workbuddy_official_model: str = "glm-5.2"
    workbuddy_official_gateway_url: str | None = None
    workbuddy_official_gateway_health_url: str | None = None
    workbuddy_official_gateway_webhook_url: str | None = None
    workbuddy_official_gateway_bearer_token: str | None = None
    workbuddy_official_probe_timeout_seconds: int = 6
    workbuddy_official_cli_timeout_seconds: int = 90

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_sqlite_database_url(value)
        return value

    @field_validator("llm_provider", "strategy_llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value: object) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_")
        aliases = {"langchain": "langchain_openai", "legacy_openai": "openai"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"mock", "openai", "langchain_openai"}:
            raise ValueError("LLM provider must be mock, openai, or langchain_openai")
        return normalized

    @field_validator("research_workflow_engine", mode="before")
    @classmethod
    def normalize_research_workflow_engine(cls, value: object) -> str:
        normalized = str(value or "langgraph").strip().lower().replace("-", "_")
        aliases = {"langgraph_shadow": "langgraph"}
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"deterministic", "langgraph"}:
            raise ValueError("Research workflow engine must be deterministic or langgraph")
        return normalized

    @field_validator("decision_embedding_provider", mode="before")
    @classmethod
    def normalize_decision_embedding_provider(cls, value: object) -> str:
        normalized = str(value or "sentence_transformers").strip().lower().replace("-", "_")
        if normalized not in {"sentence_transformers", "disabled"}:
            raise ValueError("Decision embedding provider must be sentence_transformers or disabled")
        return normalized

    @field_validator("decision_embedding_device", mode="before")
    @classmethod
    def normalize_decision_embedding_device(cls, value: object) -> str:
        normalized = str(value or "auto").strip().lower()
        if normalized not in {"auto", "cpu", "mps", "cuda"}:
            raise ValueError("Decision embedding device must be auto, cpu, mps, or cuda")
        return normalized

    @field_validator("research_cross_encoder_device", mode="before")
    @classmethod
    def normalize_cross_encoder_device(cls, value: object) -> str:
        normalized = str(value or "auto").strip().lower()
        if normalized not in {"auto", "cpu", "mps", "cuda"}:
            raise ValueError("Cross encoder device must be auto, cpu, mps, or cuda")
        return normalized

    @field_validator("wechat_favorites_llm_role", mode="before")
    @classmethod
    def normalize_wechat_favorites_llm_role(cls, value: object) -> str:
        normalized = str(value or "strategy").strip().lower().replace("-", "_")
        if normalized not in {"generation", "strategy"}:
            raise ValueError("WeChat Favorites LLM role must be generation or strategy")
        return normalized

    @field_validator(
        "langchain_structured_output_method",
        "langchain_structured_output_fallback_method",
        mode="before",
    )
    @classmethod
    def normalize_structured_output_method(cls, value: object) -> str | None:
        if value is None or str(value).strip().lower() in {"", "none", "disabled"}:
            return None
        normalized = str(value).strip().lower()
        if normalized not in {"function_calling", "json_mode", "json_schema"}:
            raise ValueError("Structured output method must be function_calling, json_mode, or json_schema")
        return normalized

    @field_validator(
        "openai_input_cost_per_million",
        "openai_cached_input_cost_per_million",
        "openai_output_cost_per_million",
        "strategy_openai_input_cost_per_million",
        "strategy_openai_cached_input_cost_per_million",
        "strategy_openai_output_cost_per_million",
    )
    @classmethod
    def validate_non_negative_pricing(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("Model prices must be non-negative")
        return value

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
