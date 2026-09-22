# Anti-FOMO 产品界面与工作流地图

Anti-FOMO 是一条研究到行动的工作流，拥有多个入口和复核表面。每个表面都说明输入、输出和证据边界，避免把 Demo、外部桥接和客户交付混为一谈。

## 主链路

`采集 → 清理 → 研究 → 对比 → 决策上下文 → 方案交付 → 跟进行动`

| 表面 | 主要工作 | 入口 | 输入 → 输出 | 复核提示 | 代码起点 |
| --- | --- | --- | --- | --- | --- |
| Collector | 收集网页、微信、文件、RSS 与 transcript | `/collector`、扩展、Mini Program | URL/文件/来源配置 → 条目、批次、来源健康 | 显示来源状态、重试与 OCR fallback；不代表来源内容已核实 | `backend/app/api/collector_*.py` |
| Inbox | 把条目变成研究问题 | `/inbox` | 条目/关键词/目标 → 报告任务和交付候选 | 先看范围、来源和缺口，再导出 | `src/components/inbox/` |
| Research Center | 管理主题、检索、档案与日常研究 | `/research` | 研究问题 + 允许来源 → 报告、主题版本、watchlist | 报告引用和 retrieval 状态不等于正式批准 | `src/components/research/` |
| Compare | 观察版本与官方来源变化 | `/research/compare`、`/competitive` | 快照/来源寄存器 → diff、stale/change、复核队列 | 厂商声明保持 `vendor_claim`，不会自动改路线图 | `src/components/competitive-intelligence/` |
| Decision Studio | 把证据放入决策上下文 | `/studio` | 主张、约束、假设 → 决策、ADR、知识空间与交付草稿 | 需要审阅者确认；本地对象不是客户签字 | `backend/app/api/decision_studio.py` |
| Product Strategy | 管理竞品、迭代卡与证据门禁 | `/competitive` | 官方观察/路线卡/操作证据 → revision、HOLD、交接索引 | `release-readiness` 与生产授权单独存在 | `backend/app/api/product_strategy*.py` |
| Architecture workbench | 准备方案架构讨论 | Inbox / report card | 研究报告 → 架构分层、NFR、依赖、风险、问题和验证动作 | 方案是可讨论草稿，须结合客户现状复核 | `backend/app/services/delivery/solution_architecture.py` |
| Focus | 在限定时间内处理和总结 | `/focus` | 目标 + 工作会话 → summary、reading list、follow-up | 本地计时器/采集器状态不可冒充后台任务完成 | `src/components/focus/` |
| Knowledge / Commercial Hub | 保存知识并连接账户与机会 | `/knowledge`、`/knowledge/accounts` | 研究/条目 → 知识卡、账户、机会、review queue | 商业价值字段是研究输入，不是销售预测承诺 | `backend/app/api/knowledge.py` |
| Tasks / WorkBuddy bridge | 导出、回调或 CLI 委派 | `/settings`、Focus、Session Summary | task payload → WorkTask、artifact、callback | webhook 可执行支持的导出任务；未配置 secret 时跳过签名校验；CodeBuddy CLI 是可选桥接 | `backend/app/api/workbuddy.py` |
| Delivery evidence | 查看修订、Office/视觉收据和交接索引 | Product Strategy panels | artifact revision → receipt、diff、audit handoff | receipt 不是人工或客户验收 | `backend/app/services/product_strategy/` |
| Mini Program / Extension | 移动入口和浏览器快速发送 | `miniapp/`、`browser-extension/` | 捕获/反馈 → API 请求、离线队列或本地 fallback | 明确显示 demo/offline；不能单独运行桌面采集器 | 各自 README |

## 状态语言

| 状态 | 意义 |
| --- | --- |
| `live/api-backed` | 当前内容来自可访问 API，但仍可能需要证据审阅 |
| `empty` | 没有可用记录；界面不应静默填入 Demo 卡片 |
| `local-demo` | 使用本地 fixture 或 mock fallback，不能写成真实同步 |
| `degraded/recovering` | 采集、检索或任务需要重试、澄清或操作员处理 |
| `evidence-gated/HOLD` | 本地代码或预览存在，但外部、Office、视觉、人工或发布证据未齐 |
| `executing/bridge` | 已把任务交给本地 webhook/CLI/gateway 桥接；结果与批准边界须单独查看 |

## 典型交接

1. 从 Collector、扩展或 Mini Program 进入一条来源，确认来源状态和权限。
2. 在 Inbox 形成问题和范围，检查报告的引用与证据缺口。
3. 在 Research/Compare/Competitive 中查看历史变化和官方来源状态。
4. 将可用结论送入 Decision Studio 与架构工作台，补齐假设、依赖、NFR 和验证动作。
5. 通过 Focus、行动卡或 WorkTask 准备下一步；任何外部写入、发送或发布都沿其实际桥接和审批边界记录。

## 代码与图

- API router 总入口：`backend/app/main.py`。
- 前端路由：`src/app/`。
- [架构图](./assets/antifomo-control-plane.svg) / [Mermaid 源文件](./diagrams/architecture.mmd)。
- [数据流图](./assets/dataflow.svg) / [Mermaid 源文件](./diagrams/dataflow.mmd)。
- [研究工作流图](./assets/workflow.svg) / [Mermaid 源文件](./diagrams/research-delivery.mmd)。
- [发布证据门禁](./diagrams/release-gates.mmd)：独立于导出、回调和 CLI 执行路径。
- 当前版本和证据词汇：[current-product-status.md](./current-product-status.md)。
