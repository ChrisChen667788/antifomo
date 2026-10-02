# Anti-FOMO × WorkBuddy：受控执行集成计划（2026-09-18）

> 这是 `2.12.0`–`2.21.0` 的权威工程计划。它把 WorkBuddy 公开资料中适合借鉴的交互和治理能力，收敛为 Anti-FOMO 的证据感知、人工审批、可回滚执行边界。版本号沿用当前开发线；仅 PR-A schema/state subset 已达到 `local_implementation`，后续计划不得写成已交付能力。
>
> 证据层级：`local_implementation`（本 checkout 可复现）→ `demo`（本地展示）→ `synthetic_benchmark`（固定样本）→ `human_acceptance` → `customer_acceptance` → `production`。WorkBuddy 官方文档是 `vendor_claim`，不是 Anti-FOMO 的验收证据。真实 pilot 是外部验收依赖，不能由本地测试或自动任务代签。

2026-09-22 已复核代码入口、验证脚本和六项官方来源。竞品事实与复核范围见 [深度对标报告](./workbuddy-deep-dive-2026-09-18.md)。截至 2026-10-02，PR-A 的 schema/state、独立控制 API、Alembic `0040` 与本地 synthetic harness 是 `local_implementation`；legacy adapter、可信 identity/permission policy、callback intent、Web UI、故障注入和 executor 仍为 **planned**。“预算”“门槛”“DoD”是目标，不是已经达到的性能、稳定性或生产承诺。

## 1. 设计不变量

1. **Ask / Plan / Agent 三态**：Ask 只读解释；Plan 生成不可变步骤和预算，等待批准；Agent 只能执行已批准步骤。签名只证明调用来源，不能替代权限和审批。
2. **副作用默认关闭**：连接器先只读；`local_write` 和 `external_write` 必须声明 scope、预算、撤销方式、dry-run 和人工批准。移动端只查看、暂停、继续、补充指令、批准或停止。
3. **幂等优先，不能承诺 exactly-once 外写**：外部系统可能在响应丢失后已经写入。每次外写携带 idempotency key；结果为 `succeeded`、`failed` 或 `unknown`，`unknown` 进入人工 reconcile，不自动重试。
4. **固定产物可复现**：稳定的是规范化输入、策略、模型/技能版本、环境指纹和交付物内容的 digest；同一模型输入不保证产生相同随机输出。模型随机输出必须保存原始产物和 manifest，比较时使用 artifact digest 与 revision diff。
5. **本地优先边界**：本计划的 SQLite 队列验收范围始终限定为单进程调度和已有租约恢复；不能称为通用分布式队列、跨实例 exactly-once 或生产消息总线。PostgreSQL/Redis/托管队列另列依赖和迁移门禁，不会因升级到 2.14 或 2.19 自动成立。
6. **HOLD 是有效结果**：证据不足、来源过期、能力未签名、预算超限、外写未知或客户验收未完成时，系统保持 `hold`，不得用降级草稿伪装完成。
7. **批准绑定内容，撤销不可复活**：approval 必须绑定 `plan_digest`、输入/产物 `content_digest`、`effects_digest`、scope、预算、approver、expiry 与 revocation epoch。任一内容、目标或权限变化都重新计划/批准；pause/resume、重复请求和进程重启不得恢复已撤销或过期的批准。每步开始前重新检查，已在外部提交的操作只能取消后续步骤并 reconcile，不能声称停止能撤回已发生的副作用。

## 2. 现有代码与复用边界

| 能力 | 当前可复用路径 | 当前证据/限制 |
| --- | --- | --- |
| WorkBuddy webhook、官方 CLI/gateway 探针 | `backend/app/api/workbuddy.py`、`backend/app/schemas/workbuddy.py`、`backend/app/services/workbuddy_adapter.py`、`scripts/workbuddy_official_doctor.sh` | `local_implementation`；仅在配置 secret 时强制签名，缺 secret 返回 `signature_bypassed_no_secret`；随后直接执行白名单导出，并可发 callback；2.12 必须统一收敛 |
| 任务执行和导出 | `backend/app/api/tasks.py`、`backend/app/services/focus_assistant.py`、`backend/app/services/task_runtime.py`、`backend/app/services/work_task_service.py`、`backend/app/services/work_tasks/*` | 已有 `POST /api/tasks` / `GET /api/tasks/{task_id}`、Focus Assistant 动作和文件导出；这些路径仍可直调 `create_and_execute_task`，导出有本地写入，不应称只读；callback 外写与旧 API 一起纳入 policy/receipt |
| 研究任务持久化、幂等、租约和恢复 | `backend/app/models/research_entities.py:ResearchJob`、`backend/app/services/research_job_store.py`、`backend/tests/test_research_job_durable_queue.py` | SQLite 单进程恢复；存在 `worker_id`、`lease_expires_at`、`idempotency_key`，不等于分布式队列 |
| append-only 操作证据 | `backend/app/models/product_strategy_operation_entities.py`、`backend/app/services/product_strategy/operation_evidence_service.py`、`backend/app/api/product_strategy_operations.py` | 已有 capability/skill/proposal/dry-run/rollback/performance/feedback/gate/audit API |
| 固定性能与稳定性测量 | `backend/app/schemas/product_strategy_operations.py:PerformanceEvidence`、`scripts/stability_concurrency_smoke.py`、`scripts/run_industry_knowledge_retrieval_ranking_benchmark.py` | 可记录本地/合成测量；不是生产 SLA |
| 技能与行业资料 | `backend/app/services/internal_skill_registry.py`、`backend/app/services/industry_skill_library.py`、`backend/app/services/decision_studio/skills.py`、`backend/tests/test_internal_skill_registry.py` | 已有本地注册、评测和 governed Skill HMAC/dry-run；2.15 统一外部 manifest、scope、撤销、过期与执行入口，不重复造一套签名状态 |
| 人工接受、Office/视觉回执 | `backend/app/services/product_strategy/human_acceptance_service.py`、`backend/app/services/product_strategy/office_evidence_service.py`、`backend/app/services/product_strategy/visual_evidence_service.py` | 本地回执不替代独立/客户接受 |
| 前端研究/WorkBuddy surfaces | `src/components/settings/workbuddy-panel.tsx`、`src/components/research/*`、`src/components/session/*` | 适合渐进增加 plan/review/receipt，不重写现有路线 |

## 3. 本次范围内的 WorkBuddy 能力映射

| 编号 | WorkBuddy 公开能力/提议 | Anti-FOMO 吸收版本 | 明确不复制的边界 |
| --- | --- | --- | --- |
| WB-1 | Task Bar、独立任务空间、并行任务 | 2.12 信封、2.14 lanes、2.17 Review Inbox | 不允许一个自然语言任务绕过审批产生副作用 |
| WB-2 | Ask / Plan / Agent 三态 | 2.13 | Agent 只执行批准的不可变 plan |
| WB-3 | Connector：授权读、写/发送再次确认 | 2.15、2.19 | 不把 token/文件/消息正文落入证据表；外写 unknown 必须 reconcile |
| WB-4 | Automation：定时、频率/时长/并发限制、失败日志 | 2.14 scheduler lane、2.19 governance | 先只读来源刷新；不承诺定时外部写入成功 |
| WB-5 | Skill / 专家 / MCP 注册与切换 | 2.15 | 签名、来源 digest、模型 revision、权限 scope 未齐则 HOLD |
| WB-6 | 模型切换与多模态任务 | 2.12 model profile、2.13 routing、2.20 模板 | 只按固定 benchmark 选路，不按厂商宣传自动切默认模型 |
| WB-7 | 本地文件操作和多格式交付 | 2.16 artifact studio、2.20 solution workbench | 文件写入限于沙盒；Office 回执和人工审阅仍必需 |
| WB-8 | 结果面板、可验收成果 | 2.16/2.17 artifact revision、review receipt | 结果存在不等于客户验收或生产部署 |
| WB-9 | 高危指令拦截 | 2.12/2.15 capability policy、2.19 tenant policy | 仅拦截规则不是完整安全审计；需回执、撤销、恢复演练 |
| WB-10 | 跨设备查看、继续、补充、停止 | 2.18 mobile continuity | 移动端不开放高风险写、凭据或批量导出 |
| WB-11 | 团队知识、ACL、评论和 AI 修订建议 | 2.17/2.19 | AI 只生成 diff/suggestion，逐条接受后才写正文 |
| WB-12 | 企业统一身份、审计、OpenAPI、Managed Agent | 2.19/2.21 仅做兼容边界 | 不是腾讯企业版接入；需企业方外部验收后才可称 pilot/production |
| WB-13 | WorkBuddy Bench 与公开任务 harness | 2.20 固定 benchmark 参考 | benchmark 结果只证明样本表现，不证明 WorkBuddy 生产 SLA |

## 4. 版本执行合同（2.12.0–2.21.0）

每版都必须先开一个小 PR，功能、迁移、测试、文档和回滚说明分开可评审；新增执行能力的 feature flag 默认关闭，证据控制 API 可以继续记录 proposal 和 receipt。工作量是估算的人日（1 人日=可提交、可复核的 8 小时），角色为后端 `BE`、前端 `FE`、平台/性能 `PE`、安全/合规 `SEC`、产品/架构 `SA`、QA。除非明确写出 `customer_acceptance`，DoD 只到本地或合成证据。

依赖顺序为 `2.12 → 2.13 → 2.14 → 2.15 → 2.16 → 2.17 → 2.18 → 2.19 → 2.20 → 2.21`；同版 PR 可以在 schema 冻结后并行，后一版不能绕过前一版的授权/恢复门禁。现有 `scripts/stability_concurrency_smoke.py` 只对固定 GET 端点做并发冒烟，不能证明新任务 POST、租户隔离、状态机或重启恢复；新增验收 harness 必须随对应版本交付。所有命令先在隔离 fixture 数据库运行，使用当前仓库配置的 Python 环境。

### 排期与第一条可开工 PR

逐版估算为 `10 + 11 + 11 + 11 + 11 + 9.5 + 12 + 14 + 18 + 14 = 121.5 人日`，包含上述开发、测试和文档工作量，不是 121.5 个日历日的交付保证；人员熟悉度、返工、平台审核、来源变化和外部客户等待需在排期时单列。每个版本结束按实测吞吐重估剩余工作。

- **第一条 PR：2.12.0 / PR-A**。原验收合同仍要求：一个 proposal、同 key 并发不产生第二个任务，并且未经批准、缺 secret、digest 改变或批准撤销时均无执行和 callback。`2026-10-02 local_implementation` 只完成 envelope/approval/receipt/model-profile schema、Alembic `0040`、独立控制 API 与状态机负例；100 次同 key 测试只验证该独立 API 不生成 `WorkTask`。WorkBuddy webhook、`/api/tasks`、Focus Assistant、callback policy 与前端兼容尚未迁移，缺 secret 的旧 webhook 仍可直接执行，因此 PR-A 整体和 2.12.0 DoD 均未完成。
- **关键依赖**：2.12 的 identity/policy/receipt 是全部执行能力的前置；2.13 冻结 plan 合同，2.14 才接入多 lane；2.15 的 scope/撤销供后续产物、移动和团队执行复用；2.16 revision 合同供 2.17 审阅使用；2.19 隔离与账本是 2.21 真试点前置。
- **可并行准备**：后端合同冻结后，前端先接 fixture；registry 清单、T1/T2/T3 数据集、Office 样本、视觉素材和威胁负例可与主线并行整理。预研或 fixture 完成不代表依赖版本已通过。
- **外部里程碑**：2.21 的本地计量、暂停/退出和验收包可独立完成；客户接受与生产运行仍需要外部范围、版本、签字/可归因回执，等待时间不计入本地开发已完成的结论。

### 2.12.0 — Task Envelope、权限边界与模型 profiles

以下条目是完整 2.12.0 的目标态。当前 PR-A schema/state subset 不满足 webhook 只创建 `proposed`、旧任务入口统一 policy、缺权限进入 HOLD、callback 先登记后批准发送、flag 关闭时仍禁止旧 POST 绕过，以及故障注入与完整 DoD。

- **目标 / WB 映射**：落地 WB-1、WB-2、WB-6、WB-9。把当前 webhook 和旧任务 API 的直接执行收敛到 `Ask|Plan|Agent` 信封；新入口在缺 secret、scope 或 approval 时 fail-closed。
- **复用与证据路径**：复用 `workbuddy.py`、`workbuddy_adapter.py`、`task_runtime.py`、`ResearchJob.idempotency_key/request_payload`、操作 evidence API；验证命令 `npm run workbuddy:doctor`、`backend/.venv311/bin/pytest -q backend/tests/test_workbuddy_adapter.py backend/tests/test_work_task_owner_boundaries.py`。
- **API/schema/state**：新增 `TaskEnvelope`（`task_id/request_id/user_id/mode/capability_key/context_digest/model_profile/budget/deadline/idempotency_key/approval_ref/rollback_ref/legacy_work_task_id`）；`Approval`（`plan_digest/content_digest/effects_digest/scope/budget/approver/expires_at/revocation_epoch`）；`TaskState = proposed|planned|approved|running|succeeded|failed|unknown|hold|cancelled|reconcile_required`；新增独立命名空间 `POST /api/task-envelopes`、`GET /api/task-envelopes/{id}`、`POST /api/task-envelopes/{id}/approve|cancel|reconcile`。一个 envelope 最多绑定一个执行用 `WorkTask`；`WorkTask` 的 `done/failed` 是旧运行结果，必须由 receipt adapter 映射，不与审批状态混用。不覆盖既有 `/api/tasks` 路由；webhook 只创建 `proposed`。
- **模型 profiles/budget/routing**：新增版本化 `ModelProfile`（provider/model/revision/temperature/max_tokens/timeout/cost ceiling/fallback order）；默认只读任务走固定 profile，超过 budget 或 profile 过期即 HOLD。随机模型不写“可复现输出”。
- **迁移/兼容**：新增 Alembic `task_envelopes/task_approvals/task_receipts/model_profiles`；approval 独立保存不可变的 digest、scope、budget、expiry 与 revocation epoch，receipt 保存状态转换链。旧 WorkBuddy payload 适配为 `proposed`，提供明确的兼容响应和迁移说明；已有 `/api/tasks` 保留读取/下载，创建接口须调用同一 policy，缺授权返回结构化错误。callback 先登记目标 host、scope 和 payload digest，批准后才能发送；不能直接重放历史任务。
- **依赖 / PR / 预算**：仅现有 SQLAlchemy/Pydantic；PR-A schema/state+migration（BE 2, SA 0.5）；PR-B webhook adapter（BE 2, SEC 1）；PR-C UI status/approval（FE 2）；PR-D tests/docs（QA 2, PE 0.5）；总计 BE4/FE2/QA2/SEC1/SA0.5/PE0.5=10 人日。
- **失败处理**：重复 idempotency 返回原 task；预算/权限/过期 profile → `hold`；执行超时 → `unknown`，禁止盲重试；外写只允许带 idempotency key。
- **性能/稳定性预算与验证**：本地 SQLite 固定 1k 信封，接收 p95 ≤2s；固定非法 schema 全部拒绝；同 key 不新增任务/执行回执，可保留单独的请求审计记录。新增 `scripts/task_envelope_benchmark.py --requests 1000 --concurrency 20 --max-p95-ms 2000` 和 webhook/旧 API/callback 故障注入；现有 GET 并发脚本仅作为旧读路径回归（结果标 `synthetic_benchmark`）。
- **回滚/恢复**：`ANTI_FOMO_TASK_ENVELOPE=0` 关闭新任务执行，只保留旧任务读取和已生成文件下载；webhook/旧 POST 不恢复无审批执行。先导出 envelope/receipt，再验证兼容快照；采用保表的 expand/contract 迁移，不执行会删除回执的 down migration。
- **DoD**：单测、迁移、前端回归、签名/权限/预算测试通过；100 次同 key 重放只有一个本地任务；plan/content/effect 任一 digest 变化、批准过期、撤销后 resume、跨用户重放全部拒绝；外写 unknown/manual reconcile 测试通过；文档注明 local implementation。

### 2.13.0 — Ask / Plan / Agent 与模型路由

- **目标 / WB 映射**：完整 WB-2、WB-6，先计划后执行；吸收 `Plan`/`Ask` 的任务体验而不开放任意 Agent。
- **复用/证据**：`research_job_store.py` 的请求快照/恢复、`research.py` API/schema、`internal_skill_registry.py`；命令 `backend/.venv311/bin/pytest -q backend/tests/test_research_job_durable_queue.py backend/tests/test_internal_skill_registry.py`。
- **API/schema/state**：`PlanStep`（顺序、依赖、capability、read/write effect、budget、timeout、rollback）；`TaskPlan` 不可变 digest；`POST /api/task-envelopes/{id}/plan|approve|execute`；计划图限制 32 步/3 层。`mode=ask|plan|agent` 与 2.12 的 `TaskState` 分开；UI 的“等待批准/执行中/完成”分别映射 `planned/running/succeeded`，不引入第二套冲突状态。
- **路由与固定 benchmark**：profiles 按任务类别（extract/summarize/research/export）绑定；每个 profile 固定 30 条脱敏样本、seed/temperature/版本、token/cost/latency/error 指标。路由只能在 allowlist fallback；模型输出不要求相同，artifact digest 必须稳定。
- **迁移/兼容**：旧任务可生成只读 plan preview，不自动 approve；`create_and_execute_task` 只能由完成统一 policy 检查的 adapter 调用；关闭 flag 不得绕过 2.12 门禁。导出产物结构兼容，创建接口行为变化由迁移说明明确记录。
- **依赖/PR/预算**：新增 plan validator 和 benchmark fixture；PR-A planner/schema（BE3/SA1）；PR-B routing/budget（BE2/PE1）；PR-C plan UI（FE2）；PR-D tests（QA2）；总 11 人日。
- **失败处理**：循环/超层数/缺 capability→hold；模型 quota/429→允许同 profile fallback 一次并记录 effective model，仍失败→hold；取消传播至未开始步骤。
- **验证/预算**：固定 30 条任务计划生成 p95 ≤ 3s、计划约束违规率 0%；路由测量 `scripts/run_industry_knowledge_retrieval_ranking_benchmark.py`，新增 `scripts/run_model_profile_benchmark.py --cases 30 --repetitions 3`；只报告 synthetic/local。
- **回滚/DoD**：`ANTI_FOMO_PLAN_MODE=0` 关闭新执行，保留 Ask/计划预览及已生成产物读取；保存 plan JSON/digest 后可恢复；固定任务的结构/约束评分目标 ≥95%，不要求模型文本相同；DoD 含最小人工审批面板和拒绝重放，批量 Review Inbox 留到 2.17。

### 2.14.0 — 并行 lanes、SQLite 写队列与只读 scheduler

- **目标 / WB 映射**：WB-1、WB-4。引入采集/研究/导出 lanes 与 schedule control，但先限制单进程 SQLite。
- **复用/证据**：复用 `ResearchJob` lease/worker 字段、`research_job_store` recovery、`backend/app/db/session.py` SQLite WAL；`scripts/stability_concurrency_smoke.py`、`backend/tests/test_research_job_durable_queue.py`。
- **API/schema/state**：`ExecutionLane`（lane_key, concurrency_limit, queue_depth, checkpoint_digest）；`ScheduleSpec`（timezone, cadence, max_runtime, max_concurrency, read_only）；`LaneJob` 状态 `queued|claimed|running|retry_wait|paused|succeeded|failed|dead_letter|cancelled|unknown`；`GET/POST /api/scheduler/specs`、`POST /api/lanes/{lane}/pause|resume`、`GET /api/lanes/{lane}/status`。
- **完成映射与计数**：`LaneJob.succeeded/failed/cancelled` 是执行终态，不能再次 claim；`dead_letter` 进入人工 HOLD，`unknown` 进入 reconcile，不自动重试。父 `TaskState` 只在全部必需步骤成功时为 `succeeded`，任一必需步骤不可恢复失败为 `failed`，执行/退避期间保持 `running`，待人工处置映射 `hold/unknown`；部分步骤成功不能提前完成整个任务。`queue_depth` 统计 queued/retry_wait/paused，`active_count` 统计 claimed/running，terminal/dead-letter/unknown 分列；状态变更、唯一 transition receipt 和计数更新在同一事务完成，重复完成回调不得重复释放 slot 或累加完成数。外写 unknown 保留目标幂等锁和未决计数，避免释放本地 slot 后误发同一操作。
- **诚实边界**：当前 worker 的支持/验收范围是单进程调度、SQLite 持久化、busy timeout 和租约恢复；本地持久恢复可以成立，但不能由此推导跨进程调度正确性、分布式队列或 exactly-once。跨实例前必须另有数据库/消息队列设计和 soak 证据。
- **迁移/兼容**：不改旧 `research_jobs` 语义；新增表和适配层；scheduler 默认只读来源刷新关闭外写；进程重启恢复有 request snapshot 才可重试，否则 dead-letter+HOLD。
- **依赖/PR/预算**：PR-A lane schema/service（BE3）；PR-B SQLite adapter/lease tests（BE2/PE1）；PR-C scheduler UI（FE2）；PR-D soak/failure injection（QA2/PE1）；总 11 人日。
- **失败处理**：指数退避上限 3 次；429/5xx 分类，4xx 非授权不重试；租约过期仅在本地事务重新 claim；外写响应丢失→unknown/manual reconcile；dead-letter 不自动清除。
- **验证/预算**：本地固定 4 lanes，队列接收 p95 ≤2s、lane 状态 p95 ≤800ms、错误率 ≤1%、配置的租约到期后恢复目标 ≤60s。新增 `scripts/lane_soak.py --lanes 4 --duration 1800` 做 CI 30 分钟 smoke；另跑 `--duration 86400` 才能产生 24 小时 soak 证据，两者不能称等效。故障注入覆盖 kill/restart、锁等待、重复 claim 与缺快照；旧 GET 脚本仅作读路径回归。
- **回滚/DoD**：`ANTI_FOMO_LANES=0`；暂停 scheduler 后仅保留已授权的手动 research job；迁移向前兼容、队列快照可导出；DoD 标注“单进程 SQLite 持久化/恢复证据”，不升级为分布式或 production 保证。

### 2.15.0 — Skill / Connector Registry 与权限撤销

- **目标 / WB 映射**：WB-3、WB-5、WB-9。把 Skill/MCP/connector 变成有签名、版本和 scope 的可审计能力。
- **复用/证据**：`internal_skill_registry.py`、`product_strategy_operations.py` 的 `CapabilityRegistration/SkillInventoryRegistration`、`operation_evidence_service.py`；命令 `backend/.venv311/bin/pytest -q backend/tests/test_internal_skill_registry.py backend/tests/test_product_strategy_artifact_acceptance_service.py`。
- **API/schema/state**：`ConnectorManifest`（connector_key, version, source_url/digest, signature_digest, capabilities, hosts, data_boundary, effect, expires_at）；`SkillState=registered|verified|expired|revoked|failed`; `POST /api/connectors/register|revoke`、`GET /api/connectors`、`POST /api/skills/{key}/renew`。
- **迁移/兼容**：旧 internal skills 保留原 registry version，先映射为 `local_only/registered`；只有通过签名、来源和 scope 验证才置 `verified`，不能因迁移自动可信。凭据只存 secret reference；未迁移 connector 不授予新执行权限。增加唯一 `(key,version,digest)`。
- **依赖/PR/预算**：HTTPS fetch 可选但默认手工登记；PR-A manifests/crypto（BE3/SEC1）；PR-B policy evaluator（BE2/SEC1）；PR-C registry UI（FE2）；PR-D negative tests（QA2）；总 11 人日。
- **失败处理**：signature/source digest mismatch、过期、scope 越权、host 不允许→拒绝并 receipt；撤销立即阻止新任务，运行中的任务在 checkpoint 停止；无网络只用已缓存且未过期 manifest。
- **验证/预算**：固定 100 manifests，register/list p95 ≤800ms；负例 100% reject；secret scan 0；`npm run security:scan`、`backend/.venv311/bin/pytest -q backend/tests/test_internal_skill_registry.py`。
- **回滚/DoD**：`ANTI_FOMO_CONNECTOR_REGISTRY=0` 强制旧 connector read-only；导出 registry snapshot 后可恢复；禁止删除 append-only revoke receipt；DoD 完成 scope/expiry/revoke/replay。

### 2.16.0 — Evidence-aware Artifact Studio 与稳定 revision digest

- **目标 / WB 映射**：WB-7、WB-8、WB-11。提供带引用锚点、diff 和可回滚 revision 的交付物。
- **复用/证据**：`product_strategy_operation_entities.py` append-only evidence、`artifact_acceptance_service.py`、`office_evidence_service.py`、`visual_evidence_service.py`；现有 Office 命令 `npm run office:roundtrip`、`npm run office:visual-baseline`。
- **API/schema/state**：`ArtifactManifest`（artifact_key, source_evidence_keys, normalized_payload_digest, renderer/version, media manifest, parent_revision）；`ArtifactRevision=generated|review_required|accepted|rejected|superseded|hold`; `GET /api/artifacts/{key}/diff`、`POST /api/artifacts/{key}/accept|reject|rollback`。
- **稳定性语义**：规范化 JSON、排序、编码、模板版本和输入证据 key 计算 digest；模型随机结果作为输入 artifact 保存，不能声称同模型同输入输出相同。revision digest 在同一产物字节/manifest 下稳定。
- **迁移/兼容**：旧导出包包一层 legacy manifest，不能回填缺失来源；原下载 URL 保持；新增 artifact/revision 表和索引。
- **依赖/PR/预算**：PR-A manifest/diff（BE3/SA1）；PR-B Office/visual bridge（BE2）；PR-C artifact UI（FE3）；PR-D render/replay tests（QA2）；总 11 人日。
- **失败处理**：缺 claim evidence→HOLD；Office render mismatch→review_required；digest mismatch→生成新 revision，不覆盖旧；回滚只指向已存在的 accepted revision。
- **验证/预算**：固定 30 artifacts，digest 计算 p95 ≤1s；Office roundtrip 100% fixture pass；`npm run office:roundtrip && npm run office:visual-baseline`；`backend/.venv311/bin/pytest -q backend/tests/test_product_strategy_artifact_acceptance_service.py`。
- **回滚/DoD**：`ANTI_FOMO_ARTIFACT_STUDIO=0`；旧导出继续可下载；artifact/revision append-only，SQLite 备份可恢复；DoD 包含字段级 diff、来源锚点、接受/拒绝回放。

### 2.17.0 — Review Inbox、批量人工审阅与 suggestion diff

- **目标 / WB 映射**：WB-8、WB-11。把可验收成果和团队修订建议放入显式人工队列。
- **复用/证据**：`product_strategy_human_acceptance.py`、`human_acceptance_service.py`、`src/components/competitive-intelligence/competitive-human-acceptance.tsx`、`src/components/inbox/research-report-review-queue-section.tsx`。
- **API/schema/state**：`ReviewItem`（artifact_revision, reviewer, required_claims, decision, reason, expected_digest）；`Suggestion`（JSON pointer, before/after, author, status）；状态 `queued|in_review|approved|rejected|returned|expired`; `GET /api/reviews/inbox`、批量 `POST /api/reviews/decide`。
- **迁移/兼容**：现有 acceptance receipt 映射为 single review item；不修改旧 receipt；AI 建议只能另存 diff。
- **依赖/PR/预算**：PR-A schema/queue（BE2）；PR-B review APIs（BE2/SEC0.5）；PR-C web/mobile-safe UI（FE3）；PR-D accessibility/negative tests（QA2）；总 9.5 人日。
- **失败处理**：并发 review 版本冲突→返回 409 + 新 revision；批量部分失败逐项回执；审阅过期回到 queue；拒绝可从 parent revision 重放。
- **验证/预算**：100 review items list/decision p95 ≤800ms，误接受率目标 0（负例）；`npm run test:frontend -- --run src/components/competitive-intelligence/competitive-artifact-acceptance.test.tsx` 加后端 review tests。
- **回滚/DoD**：`ANTI_FOMO_REVIEW_INBOX=0` 回到现有 acceptance 页面；所有决定可导出，不能删除；DoD 要求 reviewer/time/revision/reason 完整率 100%。

### 2.18.0 — Mobile Continuity（只读与低风险控制）

- **目标 / WB 映射**：WB-10。提供 PWA/小程序查看进度、暂停、继续、补充指令、批准/停止；不开放高风险写。
- **复用/证据**：`miniapp/pages/session-summary/*`、`miniapp/pages/research/*`、`src/app/session-summary/page.tsx`、existing task/research GET APIs。
- **API/schema/state**：设备绑定挑战（短期 token、设备指纹哈希）；`MobileCommand=observe|pause|resume|append_context|approve_low_risk|stop`；所有命令写 command receipt，执行仍由 server policy 决定。
- **迁移/兼容**：无设备绑定时保持 web；旧 token 不升级为 mobile capability；新增 command/receipt 表，短 token 只存 hash。
- **依赖/PR/预算**：PR-A device/session API（BE2/SEC1）；PR-B miniapp/PWA screens（FE4）；PR-C reconnect/offline queue（FE2/BE1）；PR-D e2e/accessibility（QA2）；总 12 人日。
- **失败处理**：断网命令本地标 pending，重连按 idempotency 上传；过期/重复 command 返回原 receipt；移动端不展示凭据和 payload 原文。
- **验证/预算**：固定 1000 reconnect commands，重复率 0；命令 API p95 ≤1s；`node scripts/focus_pause_resume_e2e.mjs`、`npm run miniapp:data-source-state:test`。
- **回滚/DoD**：`ANTI_FOMO_MOBILE_CONTINUITY=0`；撤销设备绑定立即使 token 失效；command log 可导出恢复；DoD 通过断网/重复/越权测试。

### 2.19.0 — Team Governance、用量账本与受控 scheduler

- **目标 / WB 映射**：WB-3、WB-4、WB-11、WB-12。补组织/项目/角色、成本/用量和连接器审计；scheduler 仍默认只读。
- **复用/证据**：`user_context.py`、`work_task_owner_boundaries.py`、`product_strategy_operation_evidence`、watchlist due/retry 逻辑 `research_watchlist_service.py`、`scripts/collector_daily_report.sh`。
- **API/schema/state**：`Organization/ProjectRole`（owner/editor/reviewer/viewer）；`UsageLedger`（task, model_profile, tokens, connector_calls, cost, status）；`SchedulerRun`（schedule, heartbeat, max_runtime, result_digest, failure_code）；租户 API 与 audit export。
- **迁移/兼容**：单用户映射 default organization；旧任务归属 demo org；账本只追加，历史成本未知标 `unattributed`。
- **依赖/PR/预算**：PR-A org/ACL（BE4/SEC1）；PR-B usage/cost ledger（BE3/PE1）；PR-C scheduler/audit UI（FE3）；PR-D isolation/load tests（QA2）；总 14 人日。
- **失败处理**：ACL deny；配额超限 HOLD；scheduler heartbeat 丢失→unknown/stop；租户账本写失败不补造成功记录，进入 reconcile。
- **验证/预算**：20 tenants/200 users/5000 ledger rows，租户读 API p95 ≤800ms、scheduler 每租户并发 ≤2、固定越权样本交叉读写 0。新增 `scripts/tenant_governance_benchmark.py --tenants 20 --users 200 --rows 5000 --max-p95-ms 800`，携带不同身份测 ACL、写入和账本对账；旧 GET 脚本不能替代此验收。
- **回滚/DoD**：`ANTI_FOMO_TEAM_GOVERNANCE=0` 停止新建组织和 scheduler，已有数据仍强制 tenant ACL；不得回落到无隔离单用户读取。org/ledger/scheduler 表可导出和 restore；DoD 含隔离、用量对账、暂停/停止/失败通知，不能仅因通过本地门槛而称生产企业版。

### 2.20.0 — Solution Architect Buddy 与固定评测

- **目标 / WB 映射**：WB-5、WB-6、WB-7、WB-8、WB-13。吸收 WorkBuddy 的自然语言规划、专家/Skill、交付面板，垂直聚焦方案架构。
- **复用/证据**：`backend/app/services/industry_skill_library.py`、`backend/tests/test_industry_knowledge_retrieval_benchmark.py`、`scripts/run_industry_knowledge_retrieval_ranking_benchmark.py`、现有 `src/components/research/research-*`。
- **API/schema/state**：`SolutionContext`（account/scenario/constraints/evidence_keys）；`ArchitectureBlueprint`（business/capability/data-model-deploy layers, ADR, risk, validation_actions）；`POST /api/solution/plan|blueprint|review`；模板版本和 evidence digest 必填。
- **模型 profiles/budget**：固定模型 profile 矩阵（planner/drafter/critic），每个模型的 token、latency、cost 上限在 manifest；路由只按 benchmark 结果和 availability，禁止宣传“最强模型自动选择”。
- **迁移/兼容**：现有研究 report 可生成 `SolutionContext` 草稿但缺证据则 HOLD；不把行业技能库内容计入项目 source coverage；导出兼容现有 Markdown/Office。
- **依赖/PR/预算**：PR-A context/blueprint schema（BE3/SA2）；PR-B planner/retrieval profile（BE4/PE1）；PR-C workbench UI（FE4）；PR-D 30-case benchmark/eval（QA3/SA1）；总 18 人日。
- **失败处理**：证据不足/模板过期/模型 unavailable→HOLD；检索低于阈值只给补证 action；导出失败保留 draft revision。
- **验证/预算**：30 脱敏场景、3 repetitions；关键字段完整率目标 ≥95%、planner p95 ≤5s、blueprint API p95 ≤2s；执行 `npm run knowledge:industry-skills:retrieval-ranking` 并保存 `PerformanceEvidence`，不写成客户指标。
- **回滚/DoD**：`ANTI_FOMO_SOLUTION_BUDDY=0`；旧 research surfaces 不变；蓝图和模型 manifest 可恢复；DoD 只有 synthetic/local benchmark，通过后仍需人审。

### 2.21.0 — Commercial Pilot Pack（外部验收依赖）

- **目标 / WB 映射**：WB-8、WB-12。准备试点计量、运行报告、SLA 草案、退出和数据导出，不把准备工作宣称为商业化完成。
- **复用/证据**：`current-product-status.md`、`docs/workbuddy-official-cutover.md`、所有 operation/audit handoff API、`scripts/workbuddy_official_doctor.sh`。
- **API/schema/state**：`PilotTenant`（scope, data_boundary, retention, contact）；`PilotRun`（plan_digest, manifest_digest, usage, errors, human_acceptance_ref, customer_acceptance_ref, exit_status）；`PilotState=planned|consented|running|paused|accepted|rejected|exited`。`GET /api/pilots/{id}/report|export` 只读取报告/已生成导出包，不改变状态；新建导出包使用受权限控制的 `POST /api/pilots/{id}/exports`。退出使用经身份认证和租户权限检查的 `POST /api/pilots/{id}/exit`，要求 `pilot.exit` scope、expected revision、reason 和 idempotency key，并记录回执。擦除另走 `POST /api/pilots/{id}/erase`，要求独立 `pilot.erase` scope 及绑定数据清单 digest 的显式批准；退出不隐式授权擦除。
- **迁移/兼容**：默认无真实客户数据；脱敏 fixture 作为 synthetic pilot；客户数据隔离并有 retention/erase runbook；不得从 public demo 自动升级租户。
- **依赖/PR/预算**：PR-A pilot schema/report（BE3/SA1）；PR-B metering/export/erase（BE3/SEC1）；PR-C operator UI（FE2）；PR-D external acceptance packet/tests（QA2/SA2）；总 14 人日。
- **失败处理**：外部 connector unknown→暂停并 reconcile；错误率/成本超预算→pause；客户拒绝→`rejected`，保留原因，不重试为 accepted。退出先停止新任务、处理未决副作用并生成退出回执；需要导出时先验证导出包。擦除需独立批准并满足 retention/保留义务，失败保留 `erase_pending/erase_failed` 回执，不把 `exited` 当作已擦除。
- **验证/预算**：本地用 3 个 synthetic tenants 验证报告、导出、退出、单独批准擦除；GET 不变更状态、无身份/跨租户/缺 scope 请求拒绝、重复 exit 不重复执行、无 erase approval 不删除任何数据。外部 3 个真实试点是**可选验收依赖**，只有每个有明确范围、版本、人工/客户签字和回执才能标 `customer_acceptance`；否则版本保持 `evidence-gated`。`npm run studio:reliability`、`npm run workbuddy:doctor`、全量后端/前端测试。
- **回滚/DoD**：`ANTI_FOMO_PILOT=0` 关闭新试点操作但保留 tenant ACL；保留期内的授权导出包可按恢复流程使用，已明确擦除的数据不承诺可恢复，也不得因回滚重新导入。删除只针对批准清单中的客户数据，最小审计索引按约定保留；DoD 是 pilot contract、计量、pause/exit、独立 erase approval、acceptance receipt 和真实证据边界齐全，不自动授予 production。

## 5. 跨版本性能、可靠性和成本门禁

以下都是**开发验收预算**，不是生产 SLA：

| 面 | 预算/目标 | 测量方式 |
| --- | --- | --- |
| 只读 API | p95 ≤800ms（固定本地数据集） | 既有读路径使用 `scripts/stability_concurrency_smoke.py --max-p95-ms 800 --max-endpoint-p95-ms 800`；新增端点加入版本 harness，记录环境指纹/样本数/版本 |
| 任务接收 | p95 ≤2s 返回 task id | 2.12 新增 POST harness，1k envelope，重复 key 和 schema reject 计入报告 |
| 研究/导出队列 | 单源 timeout 15s；429/5xx 最多 3 次退避 | failure injection + `ResearchJob` recovery tests |
| 并发 lanes | 2.14 单进程最多 4 lane；2.19 每租户 ≤2 | lane soak，SQLite 不声称跨实例 |
| 恢复 | 有有效 snapshot 时，配置的租约到期后恢复目标 ≤60s；无 snapshot 进 dead-letter | 记录 lease/heartbeat 配置、重启时点和恢复时点；`test_research_job_durable_queue.py` + 新 restart harness |
| 外写 | 不以 exactly-once 为目标；重复 key 返回原 receipt，unknown 进入 reconcile | connector fake server 注入 timeout/response loss |
| artifact | 规范化 manifest/digest p95 ≤1s；Office/visual fixture 100% pass | `npm run office:roundtrip`、`npm run office:visual-baseline` |
| 模型路由 | 每 profile 固定 30-case benchmark，记录 p50/p95、错误率、token、成本 | `scripts/run_model_profile_benchmark.py`（2.13 起） |
| mobile | 1k reconnect/duplicate commands，重复执行率 0 | `focus_pause_resume_e2e.mjs` + command fixture |
| 试点 | 运行报告/计量可对账；客户 acceptance 只有外部回执才成立 | pilot report + signed/attributable receipt |

## 6. 统一失败分类、观测和数据恢复

- `policy_denied`、`evidence_hold`、`budget_exceeded`、`capability_expired`、`source_unavailable`、`provider_timeout`、`external_unknown`、`migration_failed`、`manual_reconcile_required` 作为固定错误码。
- 每次状态变更写 append-only receipt，包含 task/plan/artifact/evidence digest、effective model profile、attempt、operator/reviewer、时间和 boundary label；禁止在日志中写凭据或完整私人文档。
- 每个版本提供 `snapshot → migrate → verify → rollback` 命令说明；SQLite 先做在线备份，PostgreSQL 迁移使用事务和回滚检查。删除/擦除只对明确授权的客户数据，审计回执保留最小必要索引。
- 外部调用的 HTTP 2xx 只说明对方返回成功，不自动成为 customer acceptance；回调超时后必须显示 `unknown`，不能用 `failed` 掩盖不确定性。

## 7. 发布门禁与贡献方式

每版必须：

1. 单测、集成、前端回归、迁移检查、lint/typecheck 通过；
2. 固定 fixture、失败注入、重启恢复、重复请求和权限负例均有报告；
3. 新模型/Skill/connector 先进入 inventory，过期和撤销测试通过；
4. 文档、截图、GIF 只展示已经存在的能力，planned 物料必须标识 `planned`；
5. 需要人工、专家或客户判断的事项保留 `HOLD`，不由自动任务代签；
6. PR body 说明版本、flag、迁移、数据恢复、性能样本和证据等级。

相关公开入口：[public roadmap](./public-roadmap.md)、[marketing overhaul](./marketing-overhaul-2026-09.md)、[current product status](./current-product-status.md)、[WorkBuddy official cutover](./workbuddy-official-cutover.md)。
