# Anti-FOMO 营销与产品叙事翻修方案（2026-09）

> 这份文档是 Anti-FOMO 的营销、产品叙事和后续商业化迭代的单一参考入口。它把 WindComic 中“真实工作流 + 有节奏的动效 + 可复核交付”的宣传方法迁移到研究/方案架构场景，同时保留 Anti-FOMO 的证据门禁。所有“已具备”“可演示”“待建设”都要按仓库代码、测试或外部验收分别标注。

## 1. 新的产品叙事

### 一句话

**Anti-FOMO 把网页、微信和本地资料里的噪声，变成有证据的判断、可讨论的方案和下一步动作。**

### 给人的感觉

用户每天真正需要的不是“再读一篇摘要”，而是三件事：

1. **知道什么值得看**：把高信号来源、历史变化、来源健康和重复信息放在一起。
2. **知道哪些结论站得住**：每个重要判断都能回到来源、版本、检索状态和审阅记录。
3. **知道下一步怎么推进**：把研究变成架构蓝图、客户问题、验证动作、会议议程和可交付文件。

新的宣传主张是：

```text
从信息焦虑，到有据可循的判断。
Collect → Research → Compare → Focus → Act
```

它不承诺“自动替你做完所有工作”，而是强调**减少寻找、核对和重新整理的摩擦，同时把人工判断放在正确的位置**。

### 面向不同角色的价值

| 角色 | 一句话价值 | 可展示的结果 | 不应夸大的部分 |
| --- | --- | --- | --- |
| 解决方案架构师 / 售前 | 把市场信号快速推进成客户可讨论的方案 | 架构就绪度、能力矩阵、ADR、集成风险、验证动作、会议议程 | 不宣称替代客户调研、评审或投标决策 |
| 行业咨询顾问 | 把来源、版本和证据组织成可以复核的研究包 | 章节证据包、对比快照、历史变化、正式文档 | 不宣称所有外部来源都实时可用 |
| BD / 产品负责人 | 从信号中筛出账户和动作，而不是只看趋势 | Watchlist、账户情报、行动卡、下一次跟进 | 不把机会评分写成成交预测 |
| 开源贡献者 | 能在本地复现、扩展和检查一条完整工作流 | Next.js + FastAPI、脚本、测试、证据门禁 | 不把本地 Demo 写成生产 SLA |

## 2. 从 WindComic 迁移的宣传方法

WindComic 的可迁移方法是“让观众看到工作被推进”，而不是堆功能名：

- **先给一个真实烦恼**：微信收藏越来越多，但会后仍回答不了客户问题。
- **再展示一条连续动作**：采集 → 清洗 → 证据检索 → 对比 → 架构 → 下一步。
- **每个镜头只讲一个状态变化**：来源进入队列、证据被固定、架构风险显现、动作卡生成。
- **把有生命力的细节留给 UI**：队列数字变化、来源健康颜色、HOLD 门禁、审阅者签名、可重放任务。
- **最后落到可检查的交付物**：Markdown、DOCX/PPTX/PDF、架构蓝图、议程和审计包。

这套方法不复制 WindComic 的角色、品牌、素材或文案，只借鉴其**镜头节奏、状态叙事、资产分层和“从输入到成片/交付”的连续感**。

### 30 秒动图 / 短视频脚本

| 时间 | 镜头 | 屏幕文案 | 动效与验收 |
| --- | --- | --- | --- |
| 0–3s | 微信、网页、文件碎片进入画面 | `信息很多，不等于判断更快` | 3 类来源以不同速度进入；不出现虚构数字 |
| 3–7s | 去重、正文提取和来源健康 | `先看来源，再看结论` | 重复卡片合并；失败源进入 `watch`，不被隐藏 |
| 7–12s | 证据透镜与章节证据包 | `每个关键判断，都能回到证据` | 引用点连到来源版本；缺证据的字段保持 `HOLD` |
| 12–17s | Compare 与历史快照 | `变化要能解释` | 两个版本左右对照，突出新增、删除和待核验 |
| 17–23s | 架构就绪度与风险矩阵 | `从研究推进到方案` | 业务、能力、数据/模型、部署四层依次亮起 |
| 23–27s | Focus / Action 卡 | `下一步，有边界地执行` | 生成验证动作、客户问题和会议议程；要求人工确认 |
| 27–30s | 产品名、链接、贡献入口 | `Anti-FOMO · Collect / Research / Compare / Act` | Logo 与仓库链接淡入，保留“本地 Demo / 证据门禁”小字 |

动效资产规范见：[Anti-FOMO signal loop SVG](./assets/antifomo-signal-loop.svg)、[GIF preview](./assets/antifomo-signal-loop.gif) 和 [Control-plane architecture](./assets/antifomo-control-plane.svg)。连接点和流动线是品牌演示，不代表线上吞吐或实时状态；README 截图仍使用真实界面截图。

## 3. 视觉与文档系统

### 视觉方向

- **主色**：矿物白背景、深海军蓝文字、低饱和青绿作为唯一强调色，少量金属色只用于“证据固定”提示。
- **构图**：左侧是人的问题和一句话价值，右侧是信息通过“证据透镜”后形成的结构化结果；避免通用 AI 紫蓝渐变、机器人、假仪表盘。
- **文字**：大标题只说一个结果，二级文字解释边界；性能和验收数据只在证据表中出现。
- **形状**：输入是碎片/来源点，研究是层叠纸张/引用线，方案是有层级的蓝图，动作是带审批状态的卡片。
- **动效**：快进只用于来源进入和状态切换；证据固定、人工审批和 HOLD 要有明显停顿，体现产品的可信度。

### 文档分层

| 层 | 读者问题 | 文档/素材 | 更新规则 |
| --- | --- | --- | --- |
| 入口层 | 这是什么、我为什么要试 | README、GitHub hero、30 秒 GIF、开源宣发文案 | 功能叙事变化时更新 |
| 体验层 | 我能看到什么工作流 | 产品截图、动图分镜、产品界面地图、Quick Start | 页面或路径变化时更新 |
| 可信层 | 为什么可以相信结果 | 证据门禁、评测、Office/视觉回执、稳定性报告 | 每次证据运行生成摘要 |
| 决策层 | 是否适合我的团队 | 白皮书、WorkBuddy 对比、商业化路线、NFR | 竞品或路线变化时更新 |
| 贡献层 | 我怎样参与 | CONTRIBUTING、开放 backlog、Issue/PR 模板 | 每个迭代列车同步 |

### README 首屏规则

1. 先放一句话价值和 4 个动词，不在首屏塞版本历史。
2. 主视觉明确标注“概念宣传图”，真实截图独立展示。
3. 在截图前放一条 30 秒闭环：`采集 → 证据 → 对比 → 方案 → 动作`。
4. 让读者在 60 秒内找到 Quick Start、产品边界、路线图和贡献入口。
5. 任何性能数字都必须链接到可复现报告，并注明本地样本/生产 SLA/人工验收的差别。

## 4. 产品架构、数据流与工作流

### 4.1 产品架构图

```mermaid
flowchart LR
  subgraph I[输入层]
    W[网页 / RSS / Newsletter]
    C[微信收藏 / 公众号]
    F[本地文件 / 扩展 / 小程序]
  end
  subgraph P[Anti-FOMO 产品层]
    Intake[采集与去重]
    Clean[正文提取与来源健康]
    Research[研究编排与检索]
    Evidence[证据账本 / 版本 / Claim Graph]
    Compare[对比、专题与 Watchlist]
    Architect[架构就绪度与方案工作台]
    Focus[Focus / Action / 交付导出]
  end
  subgraph G[治理层]
    Gate[人工评审、HOLD 门禁、权限]
    Ops[运行回执、成本、恢复、审计]
  end
  W --> Intake
  C --> Intake
  F --> Intake
  Intake --> Clean --> Research
  Research --> Evidence --> Compare --> Architect --> Focus
  Evidence -.证据状态.-> Gate
  Focus -.审批/导出.-> Gate
  Intake -.健康/重试.-> Ops
  Research -.指标/成本.-> Ops
  Gate --> Ops
```

### 4.2 数据流

```mermaid
sequenceDiagram
  participant U as 用户
  participant S as 来源适配器
  participant Q as 可恢复队列
  participant R as 研究编排
  participant E as 证据账本
  participant A as 架构工作台
  participant O as 交付/审计
  U->>S: URL / 微信收藏 / 文件
  S->>Q: canonical source + idempotency key
  Q-->>S: ready / processing / failed / retry
  S->>R: 清洗正文、来源版本、健康状态
  R->>E: claim、引用、检索回执、摘要
  E-->>R: evidence coverage / HOLD
  R->>A: 研究结果 + 账户/场景上下文
  A-->>U: 架构层、风险、ADR、验证动作
  U->>O: 人工审阅并选择导出
  O->>E: revision digest + acceptance receipt
  O-->>U: Markdown / Office / audit handoff
```

### 4.3 用户工作流

```mermaid
flowchart TD
  Start[一个待判断的问题] --> Inbox[Inbox：导入与分流]
  Inbox --> Health{来源健康？}
  Health -- 否 --> Recover[重试 / 换源 / 标记待核验]
  Recover --> Health
  Health -- 是 --> Research[研究与补证]
  Research --> Compare[对比版本与竞争信号]
  Compare --> Ready{证据和边界足够？}
  Ready -- 否 --> Hold[保持 HOLD，生成补证动作]
  Hold --> Research
  Ready -- 是 --> Blueprint[架构蓝图 / 客户问题 / ADR]
  Blueprint --> Review[人工评审]
  Review --> Focus[Focus 会话与行动卡]
  Focus --> Deliver[交付、归档、下次跟进]
```

## 5. 与 WorkBuddy 的垂直对比

### 5.1 研究范围与证据边界

本节只使用公开的一手资料。WorkBuddy 官方 Quick Start 将其定位为“全场景 AI Agent 桌面工作台”，重点能力是自然语言下达任务、自主规划与执行、并行任务、本地文件操作和可验收成果；官方产品介绍还列出多模态任务、模型切换、MCP、Skills 和高危指令拦截。[官方 Quick Start](https://www.workbuddy.ai/docs/workbuddy/Quickstart)、[官方产品介绍](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Product-Guide)

腾讯官方产品页强调 WorkBuddy 连接腾讯生态，并覆盖日常办公、代码开发和设计创意。[腾讯云产品页](https://intl.cloud.tencent.com/zh/products/workbuddy) 企业版资料进一步列出统一身份、安全操作审计、OpenAPI、连接器、企业 Skill/专家和 Managed Agents。[WorkBuddy Enterprise](https://cloud.tencent.com/product/workbuddy-enterprise)

| 维度 | Anti-FOMO | WorkBuddy | 判断 |
| --- | --- | --- | --- |
| 产品抽象 | 证据感知的研究与方案工作台 | 全场景桌面 AI Agent 工作台 | 两者在“工作台”相交，但主问题不同 |
| 输入 | 微信优先、网页、RSS、文件、扩展、小程序 | 自然语言、授权本地文件、联网、腾讯生态和开放连接器 | Anti-FOMO 的微信采集链更垂直；WorkBuddy 的入口更泛化 |
| 规划与执行 | 研究编排、可恢复队列、Focus 与人工确认 | Agent / Plan / Ask 模式、一句话任务、自主拆解、多任务并行、直接操作文件 | Anti-FOMO 应吸收“先计划再执行”的体验，而不是放开任意副作用 |
| 研究质量 | 来源版本、Claim/Evidence、检索诊断、HOLD、审阅和审计交接 | 官方资料明确有深度研究与结果交付；没有在公开 Quick Start 中核验同等粒度的证据账本 | Anti-FOMO 的差异化应继续放在可追溯判断 |
| 方案交付 | 架构就绪度、四层蓝图、ADR、集成风险、客户问题和验证动作 | 可生成文档、表格、PPT、网页等通用交付物 | Anti-FOMO 更贴近方案架构场景，WorkBuddy 更适合通用产出 |
| 生态连接 | 本地适配器、浏览器扩展、小程序、受控 connector 方向 | 腾讯文档/会议/企微/QQ 等原生连接器，开放平台提供 Buddy、专家、Skill、连接器和硬件生态 | 应优先兼容开放连接器协议，避免复制腾讯生态 |
| 团队与知识 | Claim Graph、账户上下文和审阅证据正在形成 | 团队知识空间、按角色 ACL、AI 修订建议、评论线程和企业专家 | 应吸收 suggestion/diff/accept/reject，不把 AI 修改直接覆盖正文 |
| 自动化与连续工作 | 竞品监测和 Focus 可产生运行回执，受证据门禁约束 | 定时任务、状态/停止/继续、手机端续聊和结果回传 | 先做只读监测与低风险控制，再评估外部写入 |
| 部署与商业化 | 本地优先开源 Demo，企业能力仍按证据门禁推进 | 官方提供桌面产品、Token/套餐与企业版，含统一身份、审计和 OpenAPI | Anti-FOMO 需要补齐用量、团队治理和托管边界 |
| 连续工作 | Focus、队列恢复、归档与行动卡 | 官方资料描述桌面与手机跨设备继续任务 | 可借鉴移动审批/暂停/继续，但保留本地数据边界 |
| 证据强度 | 本地代码、测试和证据回执可检查；外部客户/生产验收仍未完成 | 产品能力、套餐和客户/内部使用数字属于官方主张，不能直接等同于 Anti-FOMO 的验收证据 | 两者都要把“产品宣称”和“独立验收”分开 |

### 5.2 应该吸收什么，暂时不吸收什么

**优先吸收：**

1. **任务信封 + bounded planner**：一句话可以转成可审阅的步骤，但每步必须有能力范围、预算、超时、取消和人工确认。
2. **并行工作区**：让来源收集、竞品核验、文档编排分别运行，拥有幂等键、检查点、失败重试和统一进度。
3. **Skill / Connector 注册中心**：继续沿用 Anti-FOMO 的签名、权限和证据要求，把外部能力接入变成可审计清单。
4. **可验证成果面板**：每个输出显示来源、版本、摘要、digest、审核状态和回滚入口，而不是只提供下载按钮。
5. **跨设备的低风险动作**：手机只做查看、补充指令、暂停、批准和停止；不在移动端直接开放高风险写操作。
6. **团队用量与审计**：把运行次数、token/连接器成本、失败率、人工节省时间记录成账本，为商业化定价提供依据。
7. **Agent / Plan / Ask 三态**：`Ask` 只读解释，`Plan` 生成不可变方案等待批准，`Agent` 只能执行已批准步骤；每次状态切换生成 digest/receipt。
8. **共享知识与修订建议**：对 Claim Graph、账户和架构蓝图继承 ACL；AI 只产生 diff/suggestion，成员逐条接受/拒绝后才落正文。
9. **受控 scheduler**：先定时刷新官方来源和竞品监测，支持时区、最大运行时间、并发上限、暂停、停止、heartbeat、失败通知和从回执恢复。

**暂不直接吸收：**

- 任意桌面写入、发送消息、删除文件等副作用操作；必须先经过 connector scope、审批和 dry-run。
- 以“支持某模型/某专家”作为产品差异化；只有在固定评测和真实任务上证明收益后才进入默认路由。
- 将官方产品宣传的内部用户规模、套餐或生态伙伴数字写成 Anti-FOMO 的用户/营收证明。

### 现有 WorkBuddy 适配的修正

当前仓库已经存在 WorkBuddy webhook/CLI 健康探测和受控导出路径，但现有 webhook 仍可在签名通过后直接创建并执行导出任务。后续版本必须先引入 `task envelope → provenance → approval → execution receipt`，把历史“签名即执行”收敛为“签名只证明调用来源，执行仍受 scope、预算和人工批准约束”。公开文档应称其为**受控的导出/委派通道**，不能写成已完成腾讯官方托管或企业版接入。

## 6. 后续十个版本：可执行、可落地、可回滚

版本命名沿用当前开发线，先在 `2.12.0-development` 开始，不改变 `baseline_hybrid` 和现有发布门禁。

| 版本 | 模块 | 交付内容 | 验收门槛 |
| --- | --- | --- | --- |
| 2.12.0 | Task Envelope | 为 WorkBuddy/本地任务统一任务信封、provenance、能力清单、预算、超时、取消、幂等键和状态机 | 100 次重放无重复副作用；状态转移可审计；签名调用不能绕过审批 |
| 2.13.0 | Research Plan / Ask / Execute | `Ask` 只读、`Plan` 产出不可变步骤、`Execute` 只运行已批准步骤；计划图最大 32 步/3 层 | 20 个固定任务的计划一致性 ≥ 95%；超预算/超 scope 自动 HOLD |
| 2.14.0 | Parallel Lanes | 采集/研究/导出三类并行 lane、队列检查点、指数退避 | 4 lane 并行 24h soak；重启后无丢任务、无重复写入 |
| 2.15.0 | Skill & Connector Registry | 签名 Skill、connector manifest、read/write capability、scope、版本、来源、权限审批、撤销和凭据引用 | 未签名/过期/超 scope 一律拒绝；审计记录 100% 可回放；凭据不落库 |
| 2.16.0 | Evidence-aware Artifact Studio | 文档/PPT/网页交付物的引用锚点、revision digest、字段级 diff | 任一关键 claim 无证据时保持 HOLD；导出后 digest 稳定 |
| 2.17.0 | Review Inbox | 人工任务队列、批量审阅、批注、批准/拒绝/退回 | 审阅者、时间、版本和理由不可缺失；拒绝可重放 |
| 2.18.0 | Mobile Continuity | PWA/移动端查看、暂停、继续、补充指令和低风险审批；设备一对一绑定 | 断网重连不丢状态；移动端不暴露高风险写操作 |
| 2.19.0 | Team Governance | 组织/项目/角色、用量账本、成本分摊、连接器审计 | 租户隔离测试通过；账本与运行回执可对账 |
| 2.20.0 | Solution Architect Buddy | 行业模板、客户上下文、四层架构蓝图、会议/验证动作编排 | 30 个脱敏场景盲评；关键字段完整率 ≥ 95% |
| 2.21.0 | Commercial Pilot Pack | 试点租户、报价计量、运行报告、SLA 草案和退出/导出方案 | 3 个真实试点完成人工验收；无客户数据进入公开 Demo；Pilot 与 production 分开记录 |

### 6.1 性能与稳定性预算

这些是开发验收门槛，不是当前生产 SLA：

| 层 | 目标 | 保护措施 |
| --- | --- | --- |
| 只读 API | p95 ≤ 800ms（本地固定数据集） | 分页、缓存、索引、超时和请求追踪 |
| 任务接收 | p95 ≤ 2s 返回 task id | 先落库再异步执行；幂等键冲突返回既有任务 |
| 来源抓取 | 单源 15s 超时、最多 3 次退避重试 | 429/5xx 分类、熔断、来源级 health 状态 |
| 并行执行 | 默认最多 4 个 lane、单租户可配置上限 | 信号量、队列背压、取消传播和检查点 |
| 研究成本 | 每任务 token/连接器预算，超预算 HOLD | 预算预检、运行账本、模型路由白名单 |
| 恢复 | 进程重启后 60s 内恢复可重试任务 | durable queue、checkpoint、死信队列、replay 命令 |
| 交付一致性 | 同一输入/版本/策略产生稳定 digest | 固定 manifest、内容哈希、环境信息和版本锁 |
| 定时任务 | 默认只读来源刷新，单租户并发 ≤ 2 | 时区、最大时长、heartbeat、暂停/停止、失败通知和回执恢复 |
| 连接器 | 每次调用均可回答“谁、以什么权限、读写了什么” | capability manifest、ACL、rate limit、撤销和 append-only receipt |

### 6.2 发布门禁

每个版本必须同时满足：

- 单元、集成、前端回归、迁移和类型检查通过；
- 关键任务有固定样本、失败注入、重启恢复和重放结果；
- 新的 connector/Skill 有权限、撤销、超时、成本和审计用例；
- 文档、截图、动图只展示已经存在的能力；概念方案使用 `planned`；
- 需要人工或客户判断的事项继续保持 `HOLD`，不能由自动运行结果代签；
- 性能数字注明环境、样本数、是否为本地样本，不能写成生产 SLA。

## 7. 营销物料清单

### 已落地或可复用

- [Signal loop 动态 SVG](./assets/antifomo-signal-loop.svg)：README 首屏与社媒预览用。
- [Control-plane architecture SVG](./assets/antifomo-control-plane.svg)：架构、数据流和治理层概览。
- 真实界面截图：`docs/assets/screenshots/`。
- 概念主视觉：`docs/assets/github-hero-20260910.png`，继续标注为概念图。
- 宣发文字：更新 [open-source launch kit](./open-source-launch-kit.md) 和 [growth copy](./open-source-growth-copy.md) 后再发布。

### 建议制作的短视频版本

- `30s-signal-loop`：完整闭环，面向首次了解项目的人。
- `15s-architect-workbench`：只展示研究 → 架构 → 客户会议动作，面向售前/架构师。
- `10s-evidence-gate`：只展示证据、HOLD、人工审阅和可回放回执，面向技术评审。

三者共用同一组 UI 截图、字体、颜色和动效节奏，避免每个渠道做一套不相干的视觉。

## 8. 证据与引用

- [WorkBuddy Quick Start](https://www.workbuddy.ai/docs/workbuddy/Quickstart)：自然语言任务、自动规划、本地文件、并行任务和结果面板。
- [WorkBuddy 产品介绍](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Product-Guide)：多模态任务、模型切换、MCP、Skills、高危操作拦截和通用职场定位。
- [WorkBuddy Task Bar](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Task-Bar)：Agent / Plan / Ask、独立任务空间和并行任务。
- [WorkBuddy Connector](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector)：连接器按用户授权读取，写入/发送需要再次确认。
- [WorkBuddy Automation](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Automation-Guide)：定时任务、频率/时长/并发限制和失败日志。
- [WorkBuddy Multi-device](https://www.workbuddy.ai/document/cross-device-tasks)：桌面任务在手机端查看、继续、补充指令和停止。
- [WorkBuddy privacy policy](https://www.workbuddy.ai/document/privacy-policy)：模型/Skill/MCP/外部应用的数据处理边界；第三方处理不应被忽略。
- [Tencent WorkBuddy Bench](https://github.com/Tencent/workbuddy-bench) and [paper](https://arxiv.org/abs/2607.20911)：公开任务 harness，不等同于 WorkBuddy 生产 SLA。
- [腾讯云 WorkBuddy 产品页](https://intl.cloud.tencent.com/zh/products/workbuddy)：腾讯生态、桌面工作台和商业化入口。
- [WorkBuddy Enterprise](https://cloud.tencent.com/product/workbuddy-enterprise)：统一身份、审计、OpenAPI、连接器、企业 Skill/专家和托管智能体。
- [WorkBuddy 开放平台](https://open.workbuddy.cn/)：Buddy、专家、Skill、连接器和硬件生态入口。
- [WorkBuddy 跨设备任务](https://www.workbuddy.ai/document/cross-device-tasks)：桌面任务在手机端查看、继续、补充指令和停止。

本报告的竞品结论只覆盖公开资料能支持的范围。WorkBuddy 的内部使用、效果和商业数据若未由独立报告核验，只能作为官方主张；Anti-FOMO 的本地测试、Demo、试点和生产验收也继续分别标注。
