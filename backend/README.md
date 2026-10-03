# Anti-fomo Backend (MVP)

## Quick Start (SQLite demo mode)

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In SQLite mode, schema is auto-created on startup.

## LLM Provider

默认使用 `mock` provider。推荐通过 LangChain adapter 接入 OpenAI 或兼容网关：

```env
LLM_PROVIDER=langchain_openai
OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=<YOUR_MODEL_NAME>
LLM_FALLBACK_TO_MOCK=true
LANGCHAIN_STRUCTURED_OUTPUT_METHOD=json_schema
LANGCHAIN_STRUCTURED_OUTPUT_FALLBACK_METHOD=json_mode
# Use the current prices from your provider; blank values disable cost estimates.
OPENAI_INPUT_COST_PER_MILLION=
OPENAI_CACHED_INPUT_COST_PER_MILLION=
OPENAI_OUTPUT_COST_PER_MILLION=
```

`langchain_openai` 会按 prompt 映射 Pydantic schema，并从 `AIMessage.usage_metadata` 记录真实 token usage。`openai` 仍保留为旧 urllib 兼容路径；`mock` 保留确定性离线测试。当 `LLM_FALLBACK_TO_MOCK=true` 时，真实模型失败会自动回退 mock，保证 demo 不中断。

### AIPRO / Codex 网关配置（OpenAI 兼容）

```env
LLM_PROVIDER=langchain_openai
OPENAI_API_KEY=<YOUR_GATEWAY_API_KEY>
OPENAI_BASE_URL=https://vip.aipro.love/v1
OPENAI_MODEL=claude-opus-4-6
OPENAI_VERIFY_SSL=true
```

注意：具体可用模型取决于你的网关分组渠道。可以用下面命令先查：

```bash
curl -s "$OPENAI_BASE_URL/models" -H "Authorization: Bearer $OPENAI_API_KEY"
```

如果你同时在本机使用 Codex CLI，可按其文档配置 `~/.codex/config.toml`：

```toml
model_provider = "custom"
model = "gpt-5.3-codex"
model_reasoning_effort = "xhigh"
model_reasoning_summary = "detailed"
model_supports_reasoning_summaries = true
service_tier = "fast"

[model_providers.custom]
name = "custom"
wire_api = "responses"
requires_openai_auth = true
base_url = "https://vip.aipro.love/v1"
```

并在环境变量中设置：

```bash
export OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
```

## PostgreSQL mode (optional)

1. Update `DATABASE_URL` in `.env` to PostgreSQL.
2. Run migration:

```bash
source .venv311/bin/activate
alembic upgrade head
```

## API

- `POST /api/items`
- `POST /api/items/batch`
- `GET /api/items`
- `GET /api/items/saved`
- `GET /api/items/{item_id}`
- `POST /api/items/{item_id}/reprocess`
- `POST /api/items/{item_id}/feedback`
- `POST /api/feedback`
- `POST /api/sessions/start`
- `POST /api/sessions/{session_id}/finish`
- `GET /api/sessions/latest`
- `GET /api/sessions/{session_id}`
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/collector/plugin/ingest`
- `POST /api/collector/url/ingest`
- `POST /api/collector/ocr/ingest`
- `POST /api/collector/process-pending`
- `GET /api/collector/sources`
- `POST /api/collector/sources`
- `POST /api/collector/sources/import`
- `PATCH /api/collector/sources/{source_id}`
- `DELETE /api/collector/sources/{source_id}`
- `GET /api/collector/failed`
- `POST /api/collector/retry-failed`
- `GET /api/collector/daily-summary`
- `GET /api/collector/status`
- `GET /api/collector/daemon/status`
- `POST /api/collector/daemon/start`
- `POST /api/collector/daemon/stop`
- `POST /api/collector/daemon/run-once`
- `GET /api/collector/wechat-agent/status`
- `GET /api/collector/wechat-agent/config`
- `PUT /api/collector/wechat-agent/config`
- `GET /api/collector/wechat-agent/preview-capture`
- `GET /api/collector/wechat-agent/preview-ocr`
- `GET /api/collector/wechat-agent/health`
- `POST /api/collector/wechat-agent/self-heal`
- `POST /api/collector/wechat-agent/start`
- `POST /api/collector/wechat-agent/stop`
- `POST /api/collector/wechat-agent/run-once`
- `GET /api/workbuddy/health`
- `POST /api/workbuddy/webhook`
- `GET /api/system/llm/config`
- `POST /api/system/llm/dry-run`

OCR provider order (default `OCR_PROVIDER=auto`):
- local OCR (`ocrmac` / macOS Vision)
- OpenAI-compatible vision (when configured)
- mock OCR fallback

`POST /api/items` 的 `source_type` 支持：
- `url`
- `text`
- `plugin`（浏览器插件入口）

`GET /api/items` 支持参数：
- `mode=normal|focus`
- `goal_text=...`（focus 模式下用于目标匹配加权）

`POST /api/collector/ocr/ingest` 用于截图 OCR 入库：
- 输入：`image_base64`、`mime_type`、`source_url`（可选）、`title_hint`（可选）、`output_language`
- 输出：创建后的 `item` + OCR 提供方与置信度
- 可选：`process_immediately=false`，截图先入库，摘要与打标后台继续跑

`POST /api/collector/plugin/ingest` 用于桌面采集器同步入库：
- 输入：`source_url`、`title`（可选）、`raw_content`、`output_language`
- 输出：已处理完成的 `item`（含摘要、标签、评分）
- 可选：`process_immediately=false`，先快速入库为 `pending`，再由后台任务继续处理
- 同一来源再次提交时会比较精确原始 payload：内容未变则幂等复用，内容变化则创建新 revision

`POST /api/collector/url/ingest` 用于 URL 直连入库（非 OCR 主链路）：
- 输入：`source_url`、`title`（可选）、`output_language`
- 输出：已处理完成的 `item`（服务端自动抓取正文并生成摘要/标签/评分）
- 可选：`process_immediately=false`，适合微信/桌面自动化采集，避免同步等待大模型处理
- 可选：`refresh=true` 强制重新抓取已有来源；正文变化时复用现有 Item 并创建新 revision

`POST /api/collector/process-pending` 用于补偿处理积压状态：
- 输入：`limit`（query，默认 20）
- 输出：本次扫描/处理结果与剩余 pending 数

`POST /api/workbuddy/webhook` 用于 WorkBuddy 控制通道（webhook 入站）：
- `event_type=ping`：连通性探测
- `event_type=create_task`：触发 WorkTask（`export_markdown_summary|export_reading_list|export_todo_draft`）
- 可选 `callback.url`：任务完成后回调（成功/失败都会回调）
- 支持 HMAC-SHA256 签名校验（可选）：`WORKBUDDY_WEBHOOK_SECRET`

采集源管理接口：
- `GET /api/collector/sources`：查询采集源（支持 `enabled_only`）
- `POST /api/collector/sources`：新增/更新单条采集源
- `POST /api/collector/sources/import`：批量导入 URL
- `PATCH /api/collector/sources/{source_id}`：启停或更新备注
- `DELETE /api/collector/sources/{source_id}`：删除采集源

`GET /api/collector/failed` 返回当前失败列表（支持 `limit`）。

`POST /api/collector/retry-failed` 批量重试失败项（支持 `limit`），返回重试成功/失败统计。

`GET /api/collector/daily-summary` 生成采集日报（支持 `hours`、`limit`）：
- 返回聚合统计、优先阅读项、失败项
- 同时返回可直接导出的 `markdown`

## Content Pipeline

- `content_extractor.py`: URL fetch + extraction + cleaning
- `collector_evidence_service.py`: stable source identity + immutable raw/revision/span/transform receipts
- `llm_service.py`: abstract LLM provider (default `mock`)
- `summarizer.py`: short/long summary generation
- `tagger.py`: topic tags extraction
- `scorer.py`: value score + action suggestion
- `item_processor.py`: end-to-end item processing orchestration
- `workbuddy_adapter.py`: webhook signature verify + callback dispatch
- `task_runtime.py`: shared WorkTask execution runtime for API/webhook

### Collector evidence and degraded states

The `20261003_0041` migration adds the collector source-evidence foundation. `Item` remains the mutable API/UI projection, while `collector_source_items`, `collector_raw_assets`, `collector_document_revisions`, `collector_source_spans`, and `collector_transform_receipts` retain source identity and processing lineage. Replaying the same connector-native identity and revision is idempotent; changed raw content or parser fingerprint creates a new revision. The retained evidence rows reject in-place updates, while parent deletion remains available for governed erasure.

URL fetches no longer weaken TLS verification after certificate errors. Access/verification shells are not treated as article bodies: when all body-acquisition paths fail, the item stays `needs_body` and LLM processing does not run. Invalid model JSON produces `degraded` instead of `ready`. Submitted/fetched body text is retained in `CollectorRawAsset.raw_text`; transient fetch URLs stay outside the raw asset, and connector-generated link text uses the canonical URL. URL/plugin `Item.raw_content` and `Item.clean_content` remain cleaned compatibility projections. List responses preserve the existing `raw_content` and `llm_receipts` keys but return `null` and `[]`; detail responses retain the controlled projection and receipts.

Public URL fetches disable environment proxies and validate the connected socket peer before sending HTTP or TLS data. Browser extraction pins the initially approved hosts with Chromium host-resolver rules, rejects every other DNS name, aborts non-HTTP network schemes, and disables target-page JavaScript while freezing WebRTC and popup entry points before document scripts. This application boundary is intentionally conservative: cross-host redirects and dynamically rendered assets can be blocked, and production deployments still require an outbound network policy.

Fetch URLs are transient. Durable WeChat URLs keep only `__biz`, `mid`, `idx`, `sn`, and `chksm`; URL credentials, fragments, and session-style query parameters are removed from Item, attempt, evidence, desktop state, report, and log representations. The desktop collector refreshes a seen URL after 24 hours by default (`--refresh-seen-hours`; `0` checks every cycle).

External reader fallback is opt-in because it sends the target URL to a third party:

```env
READER_PROXY_ENABLED=false
```

This schema/service foundation does not provide an official personal WeChat Favorites API, an enterprise WeChat Customer Service connector, a durable stage-job queue, or strict claim-to-span Card Factory v2. See [the WX-0–WX-E plan](../docs/wechat-incremental-ingestion-and-card-evidence-plan-2026-10-03.md) for status, migration and acceptance boundaries.

## Tests

```bash
source .venv311/bin/activate
pytest -q
```
