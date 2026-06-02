export interface LLMConfig {
  llm_provider: string;
  llm_fallback_to_mock: boolean;
  openai_base_url: string;
  openai_model: string;
  openai_temperature: number;
  openai_timeout_seconds: number;
  openai_api_key_configured: boolean;
  strategy_openai_base_url?: string;
  strategy_openai_model?: string;
  strategy_openai_timeout_seconds?: number;
  strategy_openai_api_key_configured?: boolean;
}

export interface LLMDryRunResult {
  provider_requested: string;
  provider_used: string;
  fallback_used: boolean;
  raw_preview: string;
  parsed_preview: Record<string, unknown>;
  ok: boolean;
  error?: string | null;
}

export interface ApiHealth {
  status: string;
}
