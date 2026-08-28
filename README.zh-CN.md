# Anti-FOMO

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![Next.js](https://img.shields.io/badge/Next.js-16-black)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/ChrisChen667788/antifomo?style=social)](https://github.com/ChrisChen667788/antifomo/stargazers)

![Anti-FOMO hero](./docs/assets/github-hero.svg)

把嘈杂的网页与微信信息流，变成有证据的研报、解决方案架构蓝图、专注执行和可交付动作。

Anti-FOMO 是一个开源 AI 研究工作台，适合解决方案架构师、行业咨询顾问、BD / 售前、策略团队和需要持续盯高信号内容的人。它不是“收藏稍后读 + AI 摘要”的叠加，而是把完整闭环重新接起来：

`collect -> clean -> research -> compare -> focus -> action`

先看这里：
- [快速开始](#快速开始)
- [公开路线图](https://github.com/ChrisChen667788/antifomo/issues/1)
- [2026 竞品格局与 2.0.6 后路线图](./docs/competitive-landscape-and-post-2.0.6-roadmap-2026-07-17.md)
- [适合新贡献者的入口](https://github.com/ChrisChen667788/antifomo/issues/2)
- [微信采集可靠性 help wanted](https://github.com/ChrisChen667788/antifomo/issues/3)
- [GitHub Discussions](https://github.com/ChrisChen667788/antifomo/discussions)
- [产品白皮书](./docs/product-whitepaper.md)
- [开源宣发素材包](./docs/open-source-launch-kit.md)
- [增长文案包](./docs/open-source-growth-copy.md)

## 为什么做 Anti-FOMO

大多数信息工具通常只覆盖其中一个环节：

- 收藏
- 摘要
- 搜索
- 导出笔记

Anti-FOMO 关注的是整条工作链路：

- 把 URL、文本、Feed 和微信重场景输入收进来
- 在清洗层尽量打掉 OCR 噪声、markdown/source dump、奖项论坛和弱 vendor 推进稿
- 基于证据生成研报、对比快照、架构就绪度、历史版本和正式交付材料
- 用专注会话、行动卡、brief 和 watchlist 把研究继续推进成动作

## 为什么更容易吸引用户

- `WeChat-first`：不是泛网页收藏器，而是把微信信息环境当一等输入面，并补上无头源采集和按公众号源的健康度诊断。
- `Evidence-aware`：来源质量、章节证据配额、目标账户支撑率、官方源占比都被前台化。
- `Architecture-ready`：方案包新增架构就绪度、架构分层、干系人问题地图、决策标准、ADR 决策记录、集成依赖诊断、非功能要求和核验动作，贴近解决方案架构师的交付工作。
- `Execution-oriented`：研报不是终点，后面还有专注会话、行动卡、brief、可研、项目建议书和对客 PPT 大纲。
- `Hackable`：本地优先的 Next.js + FastAPI 架构，附带浏览器扩展、小程序外壳、采集器和可跑的测试链路。

## 大版本核心功能 / Major Version Highlights

下面按公开大版本线同时给出中文和英文说明。更完整的版本能力地图维护在 [版本历史与功能地图](./docs/release-history-and-feature-map.md)。

| 版本线 | 中文核心功能 | English core capabilities |
| --- | --- | --- |
| `0.3.x` | 研究质量基线：稳定对比/导出、历史快照、离线评估、证据门槛、章节证据包和行业方法论。 | Research quality baseline with compare/export, archive snapshots, offline metrics, evidence gates, section evidence packs, and methodology playbooks. |
| `0.4.x` | 检索底座与交付包：持久化检索索引、章节路由、黄金样本评估、招投标/产品情报和正式文档导出。 | Retrieval substrate and delivery packs with persistent retrieval index, section routing, golden evaluation, tender/product intelligence, and formal export paths. |
| `0.5.x` | RAG 质量工程：纠偏检索、生成 grounding 审查、schema-v2 切块、信源清洗、实体清理和重排控制。 | RAG quality engineering with corrective retrieval, grounding review, schema-v2 chunks, source cleaning, entity cleanup, and reranker controls. |
| `0.6.0` - `0.6.4` | 重排、交付质控与诊断控制面：CrossEncoder、重建可视化、质量评分、自修订、A/B 控制和导出趋势对比。 | Reranking, delivery quality, and diagnostics control plane with CrossEncoder support, rebuild visualization, quality scoring, self-repair, A/B controls, and export trend comparison. |
| `0.6.5` - `0.6.10` | 实验编排与运行时策略：cohort 固化、baseline 锁定、rollout gate、manifest、生效策略注册表和实际运行配置。 | Persistent experiment orchestration and runtime strategy activation with frozen cohorts, locked baselines, rollout gates, manifests, active policy registry, and effective runtime config. |
| `0.6.11` | 发布级文档与截图覆盖：主功能界面截图、截图质量门槛、manifest 和完整能力地图。 | Release-grade documentation and screenshot coverage across all primary product surfaces. |
| `0.7.0` | 采集可靠性版本：Focus 优先启动无头源采集，并展示按公众号源的健康诊断。 | Collector reliability release with headless-source-first Focus collection and per-source WeChat health diagnostics. |
| `0.8.0` | 解决方案架构就绪：架构评分、蓝图分层、集成风险、非功能要求、干系人问题和验证动作。 | Solution architecture readiness with scoring, blueprint layers, integration risks, non-functional requirements, stakeholder questions, and validation actions. |
| `0.8.1` | 微信收藏导入：预检、去重、批次持久化、队列恢复、失败重试和首页滑动处理。 | WeChat Favorites import with preview, dedupe, persistent batches, queue recovery, failed-item retry, and homepage swipe triage. |
| `0.9.0` | 解决方案架构师工作台：客户场景、干系人地图、决策标准、验证动作、下次会议议程和 Markdown 导出。 | Solution architect workbench with customer scenarios, stakeholder maps, decision criteria, validation actions, next-meeting agendas, and markdown export. |
| `1.0.0` | 本地优先微信到方案基线：打通采集、首页处理、证据研报、架构就绪、工作台产物、迁移覆盖和验证。 | Local-first WeChat-to-solution baseline connecting intake, triage, evidence-backed research, architecture readiness, workbench outputs, migration coverage, and validation. |
| `1.1.0` | 模块化架构与设计系统加固：研究 workflow 变薄、feature client/controller 拆分、研报面板拆组件、日夜模式语义主题 token 收敛。 | Modular architecture and design-system hardening with thinner research workflows, split feature clients/controllers, decomposed report panels, and semantic day/night theme tokens. |
| `1.1.1` | 可度量工作流基线：框架中立编排、单次运行指标、模型成本账本和版本化 100 条研究评测集结构。 | Measurable workflow baseline with framework-neutral orchestration, per-run metrics, a model cost ledger, and a versioned 100-case research evaluation structure. |
| `1.2.0` | LangChain 适配层：Pydantic 结构化输出、provider 真实 token usage、可配置模型价格和生成/策略模型独立路由。 | LangChain adapter with Pydantic structured output, provider-reported token usage, configurable model pricing, and independent generation/strategy routing. |
| `1.2.1` | 运行时加固：拆分模型 provider owner、持久化任务指标与成本账本、类型化观测 API 和 CI 密钥扫描。 | Runtime hardening with split provider owners, persisted job metrics/cost ledgers, typed observability APIs, and CI secret scanning. |
| `1.3.0` | 可执行 100 条研究评测：真实不可用指标、远程成本确认、JSON 产物和严格发布门禁。 | Executable 100-case research evaluation with honest unavailable metrics, cost confirmation, JSON artifacts, and strict release gates. |
| `1.4.0` | LangGraph 影子编排：协议后置、可显式选择、可衡量确定性 parity，且不自动增加生产双跑成本。 | Opt-in LangGraph shadow orchestration behind the workflow protocol with measurable deterministic parity. |
| `1.5.0` | 热点拆分与 UI 回归：后端 owner、前端 model owner、Vitest 回归和 Next.js 安全补丁。 | Hotspot decomposition, frontend owner tests, UI regression coverage, and a current Next.js security patch. |
| `1.6.0` | 发布加固：Focus 共享运行时、首屏偏好引导、双主题生产截图、深色对比度兼容和废弃 facade 包装器清理。 | Release hardening with shared Focus runtime, pre-hydration preferences, dual-theme screenshots, dark contrast compatibility, and dead facade-wrapper retirement. |
| `1.7.0` | LangGraph 生产切换：锁定 100 条评测集、零成本 deterministic/LangGraph 等价门禁、deterministic 回滚和安全 PostCSS 依赖覆盖。 | Production LangGraph orchestration with a locked 100-case evaluation set, zero-cost deterministic parity, deterministic rollback, and a safe PostCSS override. |
| `1.7.1` | 评测治理：独立复核声明与内容摘要、真实评测预算规划、默认每批最多 5 条，以及缺失定价或超预算时的运行停止保护。 | Evaluation governance with independent-review attestations, content digests, live-run budget planning, five-case batch limits, and runtime spend stops. |
| `1.7.2` | 专家意见范围修订：对 78 条评测用例补齐省级地区和明确研究主体，保持行为标签、答案锚点和来源域名不变。 | Expert-feedback scope refinement across 78 cases while preserving behavior labels, answer anchors, and source domains. |
| `1.8.0` | 专业报告质量线：主张证据账本、语义挑战者、四类文档编译器、量化决策模型、真实业务黄金样本、原生 DOCX/PPTX/PDF 交付、Office 往返诊断和视觉基线。 | Professional-report quality line with claim/evidence ledgers, semantic challengers, four document compilers, quantitative models, real-business golden samples, native DOCX/PPTX/PDF delivery, Office round-trip diagnostics, and visual baselines. |
| `1.8.1` - `1.9.1` | 发布加固、证据治理、专家校准工作流、QAW/ATAM/ADR/C4 与可执行验收证据；真实专家、盲测和客户验收仍保持阻断。 | Release hardening, evidence governance, expert-calibration workflows, QAW/ATAM/ADR/C4, and executable acceptance evidence, with real expert/blind/customer gates still blocked. |
| `1.9.2` - `2.0.0` | Decision Studio 开发线：真实语义 Notebook、来源修订与段落引用、中国正式文档合同、Claim Graph、Knowledge Space/ACL、签名 Skill、受控 MCP 和证据绑定多形态产物。当前为本地工程实现，商业发布未放行。 | Decision Studio development line with real semantic Notebooks, source revisions, Chinese document contracts, Claim Graph, Knowledge Space/ACL, signed Skills, governed MCP, and evidence-bound multi-form artifacts; commercial release remains blocked. |
| `2.0.1` - `2.0.6` | 发布程序开发线：真实数据激活、服务端计算的检索/文档/研报/安全/视觉/性能/恢复套件、不可变证据运行、哈希链审计和六版本发布控制台；人工与客户验收仍阻断。 | Release-program line with real-data activation, server-calculated quality/security/reliability suites, immutable evidence runs, hash-chain audit, and a six-version release console; human/customer acceptance remains blocked. |
| `2.0.7` - `2.2.0` | Decision Program 工程线：不可变 RC 证据、研究控制、混合检索/解析基准、证据感知编辑、企业身份/连接器、受控 Agent、行业包与客户 Pilot；外部验收仍阻断。 | Decision Program engineering line with immutable RC evidence, research control, hybrid retrieval/parser benchmarks, evidence-aware editing, enterprise identity/connectors, governed agents, vertical packs, and customer Pilots; external acceptance remains blocked. |

## 产品截图

完整的发布级截图覆盖维护在 [功能界面截图覆盖清单](./docs/feature-screenshot-coverage.md)，历代大版本能力地图维护在 [版本历史与功能地图](./docs/release-history-and-feature-map.md)。

当前截图基线于 `2026-06-19` 重新生成，共 30 张：15 个主功能界面均同时覆盖日间与夜间模式，包含分析进度、知识库、Collector、设置、专注和研究工作台的嵌套状态。

<table>
  <tr>
    <td width="50%">
      <img src="./docs/assets/screenshots/home-signal-dashboard.png" alt="首页信号面板截图" />
      <p><strong>首页信号面板</strong><br />快速判断信息价值，并进入研究、专注、收藏和运维入口。</p>
    </td>
    <td width="50%">
      <img src="./docs/assets/screenshots/research-center-dashboard.png" alt="商机情报中心截图" />
      <p><strong>商机情报中心</strong><br />集中查看 Watchlist、检索健康、历史归档、诊断和交付质量。</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./docs/assets/screenshots/inbox-research-workspace.png" alt="Inbox 研报工作区截图" />
      <p><strong>Inbox / 研报工作区</strong><br />在一个界面里完成采集、生成研报、补场景信息、审阅架构就绪度和正式文档导出。</p>
    </td>
    <td width="50%">
      <img src="./docs/assets/screenshots/research-compare-workspace.png" alt="对比矩阵截图" />
      <p><strong>对比矩阵</strong><br />横向查看多版本差异、章节证据和面向账户推进的对比信号。</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./docs/assets/screenshots/research-experiment-control-plane.png" alt="实验控制面截图" />
      <p><strong>实验控制面</strong><br />固化 cohort、锁定 baseline、审计 rollout gate，并查看实际生效的检索与研报生成运行时配置。</p>
    </td>
    <td width="50%">
      <img src="./docs/assets/screenshots/research-topic-workspace.png" alt="专题工作台截图" />
      <p><strong>专题工作台</strong><br />连续跟踪专题版本、证据密度和长期变化，而不是只看一次性结果。</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./docs/assets/screenshots/knowledge-commercial-hub.png" alt="账户情报截图" />
      <p><strong>账户情报</strong><br />把研报沉淀成甲方对象、商机、待核验队列和下一步动作。</p>
    </td>
    <td width="50%">
      <img src="./docs/assets/screenshots/collector-operations-workspace.png" alt="Collector 运维截图" />
      <p><strong>Collector 运维</strong><br />管理本地采集、源健康诊断、OCR 补录、积压恢复、自动化状态和日报导出。</p>
    </td>
  </tr>
</table>

## 当前已经能做什么

### 1. 高信号采集

- URL、纯文本、RSS、Newsletter、文件、YouTube transcript 输入
- 微信收藏导出包 / `.url` / `.webloc` / 多文件 / 剪贴板 / 原始、转义或编码后的 `mp.weixin.qq.com` 链接列表一键预检和导入，自动去重并转成首页卡片处理流
- 首页持久保留“本次微信收藏导入队列”，显示 ready / processing / failed / done 计数，支持一键重试失败条目，刷新页面后也能恢复批次，后台解析完成后自动进入卡片堆
- 可选本机 `wechat-cli` 只读适配器会周期读取文章类收藏、提取新 URL 并自动提交；未安装或未完成本机授权时，设置页明确显示 `unavailable`，不会擅自安装、重签名或修改微信
- 浏览器扩展快速采集当前页面
- 微信 URL-first 采集、无头源采集、Collector 运维、按公众号源的健康度诊断，以及作为补充 URL 发现通道的 WeChat PC Agent 工具链
- 微信正文提取会等待 `#js_content`，识别参数错误、验证、链接失效等壳页，并降级到后续提取链，避免把错误页生成摘要
- 针对截图 OCR、markdown dump、论坛奖项噪声、弱 vendor 推进稿的清洗规则

### 2. 研究工作台

- 关键词研究和结构化研报生成
- 追问 / 二次思考 / 补证后的二轮研报
- Compare Workspace、历史归档、字段 diff、导出链路
- Watchlists、Daily Brief、Knowledge Intelligence、Commercial Hub
- 面向解决方案架构师的架构就绪度评分，覆盖业务匹配、能力边界、接口依赖、安全合规和交付可行性
- 解决方案架构师工作台，自动整理客户场景、干系人关注点、能力到架构矩阵、ADR 决策记录、集成依赖诊断、验证动作和下一次客户会议议程

### 3. 检索增强与质量层

- 本地 research retrieval index，支持持久化 rebuild、resume 和 search
- retrieval index 状态面板，展示增量重建进度、父块路由和孤儿子块风险
- 增量 rebuild / 持久化 cache / recovery 的运行时优化面板
- 可选 SentenceTransformers CrossEncoder reranker adapter，并接入离线官方源召回评估
- query / routing / reranker A/B 控制面，以及 follow-up delta 离线评估
- 可持久化实验编排层，支持策略计划配置、cohort 固化、版本 baseline 锁定、gate 历史、生效策略注册表、运行时策略快照、检索/研报生成运行时配置和可审计 rollout manifest
- 章节级 retrieval pack 和 section 级证据诊断
- canonical org linking、guarded backlog、低质量研报 rewrite / backfill
- 近 3 年招投标/产品/技术参数情报包和 advisory-grade 方案交付包
- 面向中国科技项目交付的解决方案/项目建议书质量自审、自修订和显式缺口提示
- 研报生成采用“问题拆解 → 多视角检索 → 来源摘要 → 交叉验证 → 大纲 → 初稿 → 对抗式自审”，并为可研/建议书补齐方案比选、运营、综合影响、证据矩阵和假设台账
- 离线回归评估新增解决方案通过率、项目建议书通过率和交付自修订增益率
- 导出诊断新增历史趋势与相邻版本对比，能回看交付质量是否持续改善

### 4. 执行与交付

- 专注会话和会话总结导出，进入 Focus 时自动拉起混合采集链路
- 行动卡、老板简报、销售简报、外联草稿、watchlist digest
- 首页卡片堆支持左右滑动和忽略 / 收藏后自动切到下一条，并会把已处理条目从本次微信收藏队列移除
- Watchlist run history、失败重试说明、通知摘要和 Markdown digest 导出
- 可行性研究报告、项目建议书、对客 PPT、客户 brief、投标准备 memo 和执行材料导出
- 支持用“场景 / 目标客户 / 更垂直场景”重建情报包和正式文档，并保留交付质量审查记录
- 导出业务/角色层、应用能力层、模型/数据/集成层、安全/部署/运维层的架构蓝图

## 适合谁

- 解决方案架构师，把行业信号沉淀成客户可讨论的架构蓝图
- 行业咨询顾问，准备有证据的机会研究、方案建议和交付材料
- BD / 售前 / 解决方案团队
- 创业者、产品负责人和行业研究人员
- 需要持续盯公众号和高频公开信号的人
- 想要本地运行、可改造、可验证的开源研究工作台的开发者

## 快速开始

### 1. 一次性安装

```bash
git clone https://github.com/ChrisChen667788/antifomo.git
cd antifomo
npm run demo:setup
```

这会安装前端依赖、后端 Python 依赖，并创建 `backend/.env`。

### 2. 一条命令启动

```bash
cd antifomo
npm run demo:start
```

打开：

- Web：`http://localhost:3010`
- Backend API：`http://localhost:8000`

停止：

```bash
npm run demo:stop
```

### 3. 可选：微信收藏自动导入

自动导入复用本机只读命令 `wechat-cli favorites --type article`。请先按
[wechat-cli 官方说明](https://github.com/huohuoer/wechat-cli/blob/main/README_CN.md)
自行完成本机安装与授权，再指定可执行文件：

```bash
export WECHAT_CLI_BIN=/absolute/path/to/wechat-cli
npm run collector:start
```

该适配器默认增量去重并提交到与手动导入相同的持久化批次。由于不同微信版本可能涉及辅助功能、内存读取或应用签名限制，项目不会自动执行这些高权限操作。

### 4. 回归基线

```bash
cd antifomo
npm run check
npm run demo:smoke
```

如果要跑专注会话 E2E 和模拟流程：

```bash
npm run demo:focus-e2e -- --report-file .tmp/focus-e2e-report.json --artifact-dir .tmp/focus-e2e-artifacts
npm run demo:simulate
```

## 主要入口

- `http://localhost:3010/inbox`：采集、关键词研究、研报生成、正式文档导出
- `http://localhost:3010/research`：研究中心、Topics、Compare、Archive、检索增强分析
- `http://localhost:3010/focus`：专注会话和会话产物
- `http://localhost:3010/knowledge`：知识库、账户视图和 merge 工作流
- `browser-extension/chrome`：把当前页面快速送进 Anti-FOMO
- `miniapp`：微信小程序壳层
- `scripts/`：采集器、watchlist、插件验证和 smoke helpers

## 仓库结构

```text
.
├── src/                    # Next.js Web 应用
├── backend/                # FastAPI 后端、模型、服务、测试
├── miniapp/                # 微信小程序
├── browser-extension/      # Chrome 扩展
├── scripts/                # 采集器 / 自动化 / smoke helpers
├── docs/                   # 路线图、宣发素材、增长文案、设计资产
└── public/                 # 静态资源和 social preview
```

## 当前项目状态

当前代码基线：

- 本地优先、可直接运行的产品原型
- 当前开发版本：`2.9.5+20260814`（检索保证与证据运营线）
- `2.10.0-development` 竞品能力证据台账已在本地实现；它分开记录厂商声明、本地工程状态和拟议待办，不改变发布语义版本、生产默认策略或 release-readiness
- `2.10.1-development` 可复核决策上下文包可将 4 个 `build` / `integrate` / `defer` 决策初始化为仅限产品策略的可复核上下文，执行、发布与生产授权仍全部为否
- 当前本地工程切片：`2.10.2-development` 交付物验收与修订差异；它把上述上下文绑定为仅 `HOLD` 的交付物复核草案，Office、视觉和可归属人工复核证据缺失时全部保持阻断，不能改变发布门禁
- 发布晋级仍为 `blocked`：真实跨行业澄清任务与反馈、human qrels、100+30 专家校准、三行业盲测、客户验收、生产 Skill 治理以及最终 Office/视觉/安全证据尚未完成
- `2.0.1-2.0.6` 完整验证合同见 `docs/decision-studio-release-program-v2.0.1-v2.0.6.md`
- 经竞品调研优化的路线与已完成工程合同见 `docs/competitive-landscape-and-post-2.0.6-roadmap-2026-07-17.md`、`docs/decision-program-v2.0.7-v2.2.0.md`；真实外部验收仍保持阻断
- `2.2.1-2.9.5` 的证据恢复、渐进披露、实体与来源真值、账户推进、校准、检索保证和证据运营合同见 `docs/research-clarification-and-progressive-disclosure-roadmap-2026-07-26.md`
- `2.9.5` 之后的竞品研究、取舍与验收边界见 `docs/competitive-capability-observatory-v2.10.0.md`
- 已批准上下文的范围、修订/审计契约和硬性非授权门禁见 `docs/reviewable-decision-context-packets-v2.10.1.md`
- 仅 `HOLD` 的交付物验收、字段级修订差异和 Office/视觉证据边界见 `docs/artifact-acceptance-and-revision-diff-v2.10.2.md`
- LangGraph 已作为默认研究工作流，deterministic 引擎保留为即时回滚路径
- 100 条研究评测集已锁定为 `1.2.0`，离线 deterministic/LangGraph parity 为 `100/100`
- 真实 provider 评测仍要求完成修订后的独立复核，并获得明确预算批准
- Web 构建可通过
- 后端测试可通过 `npm run check`
- 现有截图基线覆盖 1.9.1 主功能界面；`/studio` 日间/夜间截图与人工视觉确认仍是 2.0 阻断项
- 历代大版本核心迭代与当前完整功能地图维护在 `docs/release-history-and-feature-map.md`
- 产品白皮书和商业化亮点文案维护在 `docs/product-whitepaper.md`、`docs/open-source-launch-kit.md` 和 `docs/open-source-growth-copy.md`
- 仓库已做开源脱敏

公开仓库刻意不包含：

- 运行时 `.env` 密钥
- 个人数据
- 本地采集日志和截图
- 私有数据库或未声明的付费信源
- 真实小程序生产凭证

## 社区与宣发资源

- 产品想法和需求：开 Discussion 或 Issue
- Bug：附带复现步骤和日志
- 代码贡献：见 [CONTRIBUTING.md](./CONTRIBUTING.md)
- 安全问题：见 [SECURITY.md](./SECURITY.md)

仓库内已附带一套可直接复用的宣发资产：

- [开源宣发素材包](./docs/open-source-launch-kit.md)
- [增长文案包](./docs/open-source-growth-copy.md)
- [产品白皮书](./docs/product-whitepaper.md)
- [公开 backlog](./docs/open-source-backlog.md)
- [GitHub hero 图](./docs/assets/github-hero.svg)
- [GitHub social preview](./docs/assets/github-social-preview.png)
- [仓库 banner](./public/repo-banner.png)

如果 Anti-FOMO 对你的工作流有价值，点一个 star 依然是最直接的支持方式。它能显著提升仓库曝光，也能帮助后续用户和贡献者更快发现它。
