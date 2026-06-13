# LangChain Adapter v1.2.0

The v1.2.0 model boundary adds LangChain without changing the deterministic research workflow engine or exposing framework objects to domain modules.

## Runtime boundary

- `LLMRunResult` is the framework-neutral result contract for content, provider/model identity, token usage, cost, attempts, and response metadata.
- Existing callers keep using `run_prompt()` and receiving JSON text. The adapter serializes validated Pydantic output back to that compatibility contract.
- `LangChainOpenAIAdapter` uses the prompt-to-schema registry and requests `json_schema` structured output by default.
- OpenAI-compatible gateways that reject `json_schema` can retry once with configurable `json_mode`.
- `mock`, legacy `openai`, and `langchain_openai` are explicit provider routes. Generation and strategy models can select routes independently.

## Usage and cost accounting

- LangChain usage is read from `AIMessage.usage_metadata`; the legacy OpenAI path reads the response `usage` object.
- `MeteredLLMService` records provider token counts when available and only estimates tokens for compatibility services that implement `run_prompt()` alone.
- Cached-input token counts are retained in ledger metadata and surfaced as cache hits.
- Prices are configuration, not hard-coded vendor facts. Configure input, cached-input, and output USD prices per one million tokens for each model route.
- If either input or output pricing is absent, the ledger reports token usage but leaves cost unpriced.

## Configuration

```env
LLM_PROVIDER=langchain_openai
LLM_MAX_RETRIES=1
LANGCHAIN_STRUCTURED_OUTPUT_METHOD=json_schema
LANGCHAIN_STRUCTURED_OUTPUT_FALLBACK_METHOD=json_mode

OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=<YOUR_MODEL_NAME>
OPENAI_INPUT_COST_PER_MILLION=
OPENAI_CACHED_INPUT_COST_PER_MILLION=
OPENAI_OUTPUT_COST_PER_MILLION=

STRATEGY_LLM_PROVIDER=langchain_openai
STRATEGY_OPENAI_API_KEY=<YOUR_STRATEGY_MODEL_API_KEY>
STRATEGY_OPENAI_MODEL=<YOUR_STRATEGY_MODEL_NAME>
STRATEGY_OPENAI_INPUT_COST_PER_MILLION=
STRATEGY_OPENAI_CACHED_INPUT_COST_PER_MILLION=
STRATEGY_OPENAI_OUTPUT_COST_PER_MILLION=
```

The next architecture step can implement a LangGraph `ResearchWorkflowEngine` adapter against the v1.1.1 workflow and metrics contracts. LangGraph should remain a selectable engine until evaluation proves a quality or reliability gain at acceptable latency and cost.
