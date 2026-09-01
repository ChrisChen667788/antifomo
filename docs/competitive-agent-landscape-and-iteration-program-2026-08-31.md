# Anti-FOMO 国内外模型 / Agent 竞品分析与 15 版本迭代方案

状态：`2.10.3–2.11.7 development control plane implemented`
研究日期：`2026-08-31`
来源失效日：`2026-09-14`
证据等级：除 Anti-FOMO 本地代码与测试外，竞品能力均为 `vendor_claim_unverified`，不是独立实测、采购结论或能力排名。

## 结论

Anti-FOMO 不应变成通用 Office 套件、AI IDE、桌面控制器或 Agent 商店。当前最值得吸收的不是竞品“能自动做更多事”，而是四类产品细节：

1. Codex / Claude Code 的长任务上下文、变更、验证与交接；
2. Gemini Enterprise / Copilot Studio 的 Agent 身份、工具清单、策略、评估和可观测性；
3. Qwen-Agent / Manus 的模型与技能可组合、任务与结果回传；
4. 千问办公、WorkBuddy、Coze 等产品从意图到可编辑交付物的低摩擦体验。

Anti-FOMO 的差异化仍应保持：

`官方/本地来源 -> 主张与证据等级 -> 决策上下文 -> 可编辑交付物与字段差异 -> Office/视觉/人工验收 -> 发布证据与独立审计`

因此本轮把后续 15 个版本统一实现为受治理控制面，同时把 Agent 动作、真实 Office/视觉验收、客户证据和生产发布继续保持为 `HOLD`。

## 方法

- 只使用产品方官网、官方文档、官方模型卡或官方代码仓库；第三方排名不能进入能力事实表。
- “最新/强”指产品方在研究日公开标注的最新、旗舰或特定任务最强信号，不表示 Anti-FOMO 已独立复现其榜单。
- 每项保留来源 URL、观察时间、14 天失效期、来源摘要、厂商主张、本地对照、风险及 `build / integrate / defer / explicitly_not_copy` 决策。
- 自动化每周检查一次，严格于“最晚两周一次”；页面变化只产生人工复核 Issue，不自动修改路线图、代码或发布状态。
- 模型质量必须按 Anti-FOMO 的中文商业研究、证据引用、长文交付物、工具权限、延迟和成本任务集重新评测，不能从通用榜单直接推导。

## 最新模型与 Agent 信号

| 产品 / 平台 | 研究日可确认的模型信号 | 官方 Agent 拳头能力 | 对 Anti-FOMO 的决策 |
| --- | --- | --- | --- |
| [OpenAI GPT-5.6 / Codex](https://openai.com/index/gpt-5-6/) | 官方将 GPT-5.6 Sol 定位为旗舰，Terra 为平衡档、Luna 为高吞吐经济档；[GPT-5.3-Codex](https://developers.openai.com/api/docs/models/gpt-5.3-codex) 为专用 Agent 编码模型。 | 并行 Agent、长任务、代码/测试/评审、后台计划任务、计算机与工具使用。 | `integrate` 任务上下文、变更验证、交接和模型分层；`explicitly_not_copy` 任意代码/终端执行。 |
| [Anthropic Claude Opus 5](https://www.anthropic.com/news/claude-opus-5) / [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started) | 官方将 Opus 5 定位为 Claude Pro 最强模型，并强调长运行 Agent、编码与专业工作。 | 终端项目上下文、复杂长任务、自我验证、企业平台部署。 | `integrate` 长任务复核和验证习惯；`explicitly_not_copy` 无边界本地执行。 |
| [Google Gemini](https://deepmind.google/models/model-cards/) / [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents) | 官方模型卡列出 Gemini 3.7 Flash（复杂 Agent 任务规模化）和 Gemini 3.1 Pro 等当前系列。 | Agent 身份、注册表、工具、策略、托管运行时、评估、追踪与可观测性。 | `build` 技能/模型台账、权限预览、评估与审计；`defer` 通用企业 Agent 平台。 |
| [Microsoft Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio) | 模型可配置；本分析不将某一底座模型混同为平台能力。 | 低代码 Agent、测试集、评估、发布审批、连接器治理、运行监控。 | `build` 版本验收包、权限、审批、监控；`explicitly_not_copy` 大而全连接器市场。 |
| [Qwen-Agent](https://github.com/QwenLM/Qwen-Agent) | 官方仓库在 2026-02-16 记录 Qwen3.5 与 Agent 示例；具体可用模型仍需环境复核。 | 工具调用、规划、记忆、Browser/Code Interpreter 示例和模型可替换框架。 | `integrate` 模型/工具协议；生产前必须沙箱、权限与真实任务评测。 |
| [扣子 Coze](https://docs.coze.cn/what_is_coze) | 多模型平台，不能把可选模型当作扣子自身的固定能力。 | 自然语言拆解、Agent 编排、代码生成、预览和部署。 | `build` 更低摩擦的提案/预览；`explicitly_not_copy` 无审查的一键部署。 |
| [Manus API v2](https://open.manus.ai/docs/v2/introduction) | 观察到的官方 API 文档未承诺固定单一底座模型，因此模型身份保持 `unknown`。 | 多步骤任务、项目上下文、文件、webhook、自定义技能和结果交付。 | `build` 可复核外部结果回传；不自动触发外部动作。 |
| [百度文心大模型](https://cloud.baidu.com/product/model.html) / DuMate | 官方产品页在研究日展示文心 5.1、ERNIE 4.5 小模型和 X1.1 等信号。 | 中文、多模态、推理及桌面办公 Agent。 | `integrate` 中文模型候选评测；`defer` 桌面文件/应用控制。 |
| [腾讯混元](https://cloud.tencent.com/announce/detail/2301) / WorkBuddy / QClaw | 官方下线公告建议旧模型迁移至 Hy3 preview 等新版；实际账号可用模型需 API 再验证。 | 办公 Agent、任务编排、即时通信入口、本地设备任务。 | `integrate` 受控结果回传；`explicitly_not_copy` IM 远程设备执行。 |
| [DeepSeek 官方组织](https://github.com/deepseek-ai) | 官方仓库可确认 V3/R1、Agent 集成清单等公开资产，但本轮未找到足够稳定的一手产品页证明新的统一旗舰 Agent 版本。 | 开源模型与集成生态。 | `integrate` 为模型候选；保持 `unknown`，不引用第三方“V4”信息升级路线图。 |

## 核心功能对比

| 维度 | 领先竞品表现 | Anti-FOMO 当前表现 | 结论 |
| --- | --- | --- | --- |
| 端到端任务执行 | Codex、Claude Code、Manus、Coze 强调从指令到动作或交付。 | 有任务、Focus、Action Card、适配器和受控提案边界；通用执行受限。 | 竞品更强；Anti-FOMO 应只补提案、权限、dry-run、回放与回滚。 |
| 企业 Agent 治理 | Gemini Enterprise、Copilot Studio 在身份、工具注册、策略、发布和观测上更完整。 | 已有 evidence/release gate、审计与职责分离，但通用 Agent 生命周期较窄。 | 竞品更强；优先补模型/技能台账、权限预览、运行证据。 |
| 中文商业研究与决策证据 | 通用 Agent 擅长生成与执行，但来源、主张、修订和发布证据常分散。 | 来源等级、决策上下文、文档合同、修订差异、验收与发布门禁形成连续链。 | Anti-FOMO 的主要优势，应继续加深而非泛化。 |
| Office/视觉交付 | GPT-5.6、Opus 5、Manus、千问办公强调文档、演示和视觉产物质量。 | 有模板、导出和 2.10.2 HOLD 控制面；真实 Office/视觉/具名验收仍缺。 | 竞品更强；2.10.5–2.10.7 必须以真实证据补齐。 |
| 模型与工具生态 | Qwen-Agent、Gemini、Copilot Studio、Coze 更开放或更广。 | 多模型配置和工具边界存在，但缺统一的任务级模型路由证据与 Agent 注册表。 | 先做证据化模型选择，不做无约束插件市场。 |
| 可回溯性与失败闭环 | 企业平台通常有日志和管理面。 | 本地证据摘要、revision、撤销、HOLD、fail-closed 和 release evidence 是强项。 | Anti-FOMO 有明确差异化，但仍需真实 rollback/shadow/独立审计。 |
| 客户与生产证据 | 成熟平台有部署与客户生态主张。 | 本地测试覆盖较高；真实任务、qrels、专家盲评、客户、>=30 shadow、漂移和回滚证据不足。 | Anti-FOMO 最大短板；不能用代码完成度代替。 |

## Anti-FOMO 优势

1. 来源、主张、本地实现、人工验收和生产发布被明确分层，降低“生成即事实、测试即上线”的混淆。
2. 面向中文行业研究、客户/招投标/技术决策文档的结构化链路比通用 Agent 更聚焦。
3. revision、digest、撤销、职责分离、HOLD 与 release-readiness 的 fail-closed 组合形成较强审计骨架。
4. 本地优先与显式权限边界更适合处理个人知识、微信收藏和敏感商业材料。
5. 已有 Research / Focus / Knowledge / Decision Studio / Product Strategy 多表面闭环，不需要从零构建任务对象。

## Anti-FOMO 短板

1. Office/视觉交付物仍缺真实应用处理、渲染检查和具名独立验收。
2. Agent 身份、模型/技能注册、工具权限预览、预算、dry-run、回放和回滚没有达到成熟企业平台的广度。
3. 模型选择仍缺统一的中文真实任务集、质量/延迟/成本路由与持续回归证据。
4. 公开演示资产、移动视口与性能证据此前覆盖不完整，物理真机仍需单独补测。
5. 真实用户任务、qrels、专家盲评、客户反馈、shadow、漂移和独立审计证据不足，production 继续 `blocked`。
6. ModelScope 默认分支仍是旧且无共同祖先的 `master`；当前安全同步只能更新 `main`，默认展示需要平台侧改默认分支或另行授权破坏性迁移。

## 2.10.3–2.11.7 十五版本计划

以下“控制面已实现”只表示本地 schema/API/UI/初始化/revision/门禁已经有代码与测试；不是相应外部功能、Office/视觉验收或生产发布完成。

| 版本 | 开发切片 | 本地交付 | 必须保持的证据门禁 |
| --- | --- | --- | --- |
| 2.10.3 | 受批准执行提案 | 上下文、权限、影响、dry-run、回滚要求 | 无具名执行批准不得动作 |
| 2.10.4 | 产品策略来源变更复核 | 官方来源寄存器、内容摘要、unknown/stale/change 信号 | 只进人工复核队列 |
| 2.10.5 | Office 证据收据 | 文件/版本/来源/渲染证据合同 | 真实 Office 处理与独立复核 |
| 2.10.6 | 视觉验收与修订差异 | 桌面浏览器、移动视口、视觉清单、字段 diff | 浏览器截图不得冒充真机/Office/人工验收 |
| 2.10.7 | 具名人工验收记录 | 批准、拒绝、退回、职责分离事件 | 匿名指令不得成为验收人 |
| 2.10.8 | 发布证据桥接 | 只读关联 release-readiness 与未决证据 | 不改变 baseline_hybrid / blocked |
| 2.10.9 | Agent 技能与模型边界台账 | 模型/技能/工具/风险/禁止动作 | 未签名、未评测、未授权不得运行 |
| 2.11.0 | 工具权限预览与 dry-run | allowlist、参数、预算、幂等、失败闭环 | dry-run 不产生外部副作用 |
| 2.11.1 | 回放与回滚演练 | 事件包、幂等键、异常与回滚记录 | 需隔离环境与独立复核 |
| 2.11.2 | 性能与成本证据基线 | 环境指纹、延迟、样本、成本假设、阈值 | 本地一次运行不得称 SLA |
| 2.11.3 | 桌面/移动证据 | 可复现截图、视口元数据、性能 JSON | 移动视口不得称物理真机 |
| 2.11.4 | 模型与 Agent 能力观察 | 本文、官方来源矩阵、14 天时效 | 厂商主张不等于独立验证 |
| 2.11.5 | 真实任务与反馈 | 同意、脱敏、qrels、盲评、反馈合同 | 不伪造用户、专家或客户证据 |
| 2.11.6 | 双周内自动竞品监测 | 每周 GitHub Action、artifact、复核 Issue | 不自动改结论、代码或发布 |
| 2.11.7 | 独立审计交接 | 摘要链、风险、职责和未决证据索引 | 交接包不等于审计通过 |

## 自动监测策略

- 工作流：`.github/workflows/competitive-monitor.yml`
- 频率：每周一 `02:23 UTC`，也支持手动运行；最坏间隔 7 天，小于要求的 14 天。
- 输入：`config/competitive-source-register.json`，当前合并上一轮 6 项指定竞品与本轮 7 项模型/Agent 平台，共 13 个官方来源观察对象。
- 输出：JSON + Markdown artifact，保留官方来源可用性、内容摘要、观察/失效时间、核心能力、本地对照、决策和风险。
- 变化、过期、基线缺失或抓取失败时：创建或更新一个 `[competitive-watch]` 人工复核 Issue。
- 禁止：自动改路线图、自动写业务代码、自动执行 Agent、自动验收 Office/视觉交付物、自动发布。

## 发布边界

- `baseline_hybrid` 仍是唯一生产默认。
- 2.10.3–2.11.7 的本地控制面不会改变现有 release-readiness 的 `blocked` 状态。
- 浏览器桌面/移动视口和性能截图是本地复现证据；没有物理设备时不得称“真机测试”。
- 真正晋级仍需：真实 Cross Encoder、固定队列、同 digest 独立 reviewer/approver/operator、至少 30 样本 shadow、漂移、回滚、真实任务/反馈、Office/视觉/安全证据和独立审计交接。
