# Anti-fomo Demo

Next.js + FastAPI MVP for:
- Inbox (URL / text input)
- Feed (single-card decision flow)
- Item detail + feedback
- Focus session (25/50 min)
- Session summary + export tasks
- Saved list

## Current status (2026-04-21 / v0.2.0)

README 顶部这组能力描述对应的是项目起始 MVP，不再代表当前系统边界。

当前代码基线已经扩展到：
- 研究中心、Compare Workspace、Tracking Topics、版本历史与字段 Diff
- Watchlists、Daily Brief、扩展导出任务
- URL-first 微信采集链路、Collector 运维、Wechat PC Agent
- Knowledge Intelligence / Commercial Hub
- 多格式输入（RSS / Newsletter / File / YouTube transcript）
- 研报 follow-up 的本地 retrieval index 最小版本，支持增量补证片段命中与证据回链

当前总计划与阶段回顾见：

`docs/development-plan-refresh-2026-04-03.md`

Phase 0 推荐回归基线：

```bash
npm run check
npm run demo:smoke
npm run demo:focus-e2e -- --report-file .tmp/focus-e2e-report.json --artifact-dir .tmp/focus-e2e-artifacts
npm run demo:simulate
```

## 1) One-time setup

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:setup
```

This installs frontend deps + backend Python deps, and creates `backend/.env`.

## 2) One-command start (recommended)

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:start
```

This starts backend + frontend in background and opens `http://localhost:3000`.
Stop all with:

```bash
npm run demo:stop
```

## 3) Run backend (manual mode)

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:backend
```

Backend runs at `http://localhost:8000`.
默认 `LLM_PROVIDER=mock`，如需切到真实模型可在 `backend/.env` 设置 `LLM_PROVIDER=openai` 与对应 `OPENAI_*` 参数。

## 4) Run frontend (manual mode)

In another terminal:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:frontend
```

Frontend runs at `http://localhost:3000`.

## 5) Demo flow checklist

1. Open `http://localhost:3000/inbox`, submit URL or text.
2. Open `http://localhost:3000`, check Feed cards and click like/ignore/save/open detail.
3. Open one item detail, click feedback + reprocess.
4. Open `http://localhost:3000/focus`, start and finish a session.
5. Open `http://localhost:3000/session-summary`, generate markdown/reading-list/todo.
6. Open `http://localhost:3000/saved`, verify saved list.

## 6) Chrome extension quick-send

Extension project:

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/browser-extension/chrome`

Use it to send current page into Anti-fomo with `source_type=plugin`.
Installation and usage: `browser-extension/README.md`.

## 7) WeChat Mini Program demo

Mini program project is ready at:

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/miniapp`

Run backend first:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:backend
```

Then open WeChat DevTools and import `miniapp` directory.
项目当前配置了一个可用的 `appid`（见 `miniapp/project.config.json`），你也可以替换成自己的 AppID。
在本地调试时，建议在开发者工具中关闭合法域名/TLS 校验以访问 localhost。
Detailed guide: `miniapp/README.md`.

## 8) Optional: API smoke test

Keep backend running, then in another terminal:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:smoke
```

## 8.1) Optional: Focus runtime E2E + diagnostics

If frontend is already running on `http://127.0.0.1:3000`, you can run:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:focus-e2e -- --report-file .tmp/focus-e2e-report.json --artifact-dir .tmp/focus-e2e-artifacts
```

默认行为：
- 脚本会自起一个隔离后端到 `http://127.0.0.1:8011`
- 输出结构化报告 `.tmp/focus-e2e-report.json`
- 在 `.tmp/focus-e2e-artifacts` 里保存页面截图、HTML 快照、页面状态快照和隔离后端日志

CI 里的 `focus-e2e` job 也会上传同名 artifact：`focus-e2e-artifacts`。

CI 本地回放和 artifact 排障说明见：

`docs/ci-troubleshooting.md`

## 8.2) Optional: Audit low-quality research reports

If you want to pull the worst stored research reports for title/summary tuning:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run research:audit:low-quality
```

默认会输出：
- `.tmp/research_low_quality_audit.json`
- `.tmp/research_low_quality_audit.md`

## 8.3) Optional: Rewrite low-quality stored research reports

If you want to rewrite the worst stored reports with the latest cleanup rules:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run research:rewrite:low-quality
```

默认会基于 `.tmp/research_low_quality_audit.json` 选前 10 条，并输出：
- `.tmp/research_low_quality_rewrite_report.json`
- `.tmp/research_low_quality_rewrite_report.md`

## 9) WeChat 30篇实测（你这轮需求）

说明：系统不能直接读取你私有微信账号数据；你需要提供你可浏览的公众号文章链接（`mp.weixin.qq.com/s?...`）列表。

方式 A（推荐，快）：
1. 打开 `http://localhost:3000/inbox`
2. 在“批量 URL 输入（每行一个）”粘贴 30 条链接
3. 点击“批量提交 URL”，等待状态变为 `ready`

方式 B（命令行自动生成报告）：
1. 把 30 条链接放到 `.tmp/wechat_urls.txt`（每行一个）
2. 运行：

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:wechat-test
```

执行后会生成报告：`.tmp/wechat_batch_report.md`

## 10) Database modes

Default is zero-dependency SQLite in `backend/anti_fomo_demo.db`.

If you want PostgreSQL:
1. Set `DATABASE_URL` in `backend/.env`
2. Run migrations:

```bash
cd backend
source .venv311/bin/activate
alembic upgrade head
```

## 11) 用现有17条做端到端流程模拟

1. 把 17 条 URL 放到 `.tmp/wechat_urls_17.txt`（每行一个）
2. 执行：

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:simulate
```

输出报告：`.tmp/mvp_simulation_report.md`  
包含：反馈闭环、Focus Session、Session Summary、3 类 WorkTask 导出结果。

## 12) 全天候采集（电脑端采集器 + 小程序OCR）

### 12.1 电脑端常驻采集器（推荐主链路）

采集器脚本：

`scripts/desktop_wechat_collector.mjs`

特点：
- 支持循环运行（daemon）
- 优先从后端采集源 API 读取监控链接（`/api/collector/sources`）
- 支持从源页面发现新文章链接（含 `mp.weixin.qq.com/s/...`）
- 正文足够时走同步 `plugin/ingest`，立即生成摘要/标签/评分
- 正文不足时走 `url/ingest`（服务端二次正文抽取），不再依赖截图 OCR
- 自动去重并记录状态（`.tmp/wechat_collector_state.json`）

准备源列表：

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/.tmp/wechat_collector_sources.txt`

每行一个 URL（可放公众号文章页、目录页、聚合页）。
说明：当你在 Web `/collector` 或小程序 OCR 页面里配置了采集源后，采集器将优先使用 API 源列表；仅在 API 不可用或为空时回退到该文件。
可将文件中的历史链接一次性同步到 API：

```bash
npm run collector:sync-sources
```

启动：

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run collector:start
```

停止：

```bash
npm run collector:stop
```

查看守护进程状态：

```bash
npm run collector:status
```

单次执行（调试）：

```bash
npm run collector:once
```

补偿处理积压 `pending`（手动）：

```bash
npm run collector:flush
```

产物：
- 日志：`.tmp/collector.log`
- PID：`.tmp/collector.pid`
- 每轮报告：`.tmp/wechat_collector_latest.md`
- 日报导出：`.tmp/collector_daily_summary.md`

手动生成日报（Markdown）：

```bash
npm run collector:daily
```

设置页新增 `Collector 运维面板`（Web）：
- 刷新 24h 状态
- 补偿 pending
- 重试 failed
- 生成并复制日报 Markdown

新增 `Collector` 页面（Web）：
- 采集源增删改查（单条/批量导入/启停/删除）
- 采集运维（状态、补偿、重试、日报）
- 守护进程控制（启动 / 停止 / 单轮执行 / 日志尾部）

### 12.3 微信 PC 全自动 Agent（实验版）

目标：尽量接近“全流程自动化”，自动点击微信 PC 公众号列表并入库（URL 优先，OCR 回退）。

脚本：

`scripts/wechat_pc_full_auto_agent.py`

默认配置文件（首次启动自动生成）：

`/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo/.tmp/wechat_pc_agent_config.json`

启动 / 停止 / 状态：

```bash
npm run wechat-agent:start
npm run wechat-agent:stop
npm run wechat-agent:status
```

单次执行：

```bash
npm run wechat-agent:once
```

前置权限（macOS）：
- 给运行终端（Terminal / iTerm / IDE）开启 `辅助功能`
- 开启 `屏幕录制`

Web 与小程序 `Collector` 页面都已提供该 Agent 的状态与启停按钮：
- `/api/collector/wechat-agent/status`
- `/api/collector/wechat-agent/config`
- `/api/collector/wechat-agent/config` (PUT)
- `/api/collector/wechat-agent/preview-capture`
- `/api/collector/wechat-agent/preview-ocr`
- `/api/collector/wechat-agent/health`
- `/api/collector/wechat-agent/self-heal`
- `/api/collector/wechat-agent/start`
- `/api/collector/wechat-agent/stop`
- `/api/collector/wechat-agent/run-once`

新增运维能力：
- `loop_interval_sec` 可在配置中调整常驻扫描间隔（20~3600 秒）
- `health_stale_minutes` 可配置“多久无新周期即视为异常”
- 状态接口返回最近一轮结果（submitted / failed / skipped_seen / skipped_low_quality / last_cycle_error）

可选自动拉起（后端启动时）：
- 调试期建议保持 `backend/.env` 中 `WECHAT_AGENT_AUTO_START=false`
- 仅在导航坐标和采集链路稳定后，再手动改成 `true`

### 12.2 手机端小程序 OCR 入口（备用链路）

小程序路径：
1. 打开 `设置` 页
2. 点击 `打开 OCR 采集器`
3. 选择公众号截图并提交

后端接口：
- `GET /api/collector/sources`
- `POST /api/collector/sources`
- `POST /api/collector/sources/import`
- `PATCH /api/collector/sources/{source_id}`
- `DELETE /api/collector/sources/{source_id}`
- `POST /api/collector/plugin/ingest`
- `POST /api/collector/url/ingest`
- `POST /api/collector/ocr/ingest`
- `POST /api/collector/process-pending`
- `GET /api/collector/failed`
- `POST /api/collector/retry-failed`
- `GET /api/collector/daily-summary`
- `GET /api/collector/status`

说明：
- 小程序本身不能在后台 24x7 自动浏览微信主 App 的公众号流；
- 推荐做法是：电脑端采集器常驻，小程序负责截图补录与状态查看。
- 微信 PC Agent 与桌面采集器现在默认使用“快速入库 + 后台处理”路径，避免同步等待摘要生成而卡住自动化流程。

## 13) WorkBuddy 控制通道（Webhook / Callback）

后端新增适配层：
- `POST /api/workbuddy/webhook`：接收 WorkBuddy 控制命令
- `GET /api/workbuddy/health`：查看通道状态

当前支持：
- `event_type=ping`：连通性测试
- `event_type=create_task`：触发 WorkTask  
  `task_type` 支持：`export_markdown_summary` / `export_reading_list` / `export_todo_draft`

可选签名校验（HMAC-SHA256）：
- `WORKBUDDY_WEBHOOK_SECRET`
- `WORKBUDDY_SIGNATURE_HEADER`（默认 `x-workbuddy-signature`）
- `WORKBUDDY_TIMESTAMP_HEADER`（默认 `x-workbuddy-timestamp`）
- `WORKBUDDY_SIGNATURE_TTL_SECONDS`（默认 `300`）

可选任务回调（Anti-fomo -> WorkBuddy）：
- webhook 请求中传 `callback.url`
- 或配置默认 `WORKBUDDY_DEFAULT_CALLBACK_URL`
- 可配 `WORKBUDDY_CALLBACK_BEARER_TOKEN`
