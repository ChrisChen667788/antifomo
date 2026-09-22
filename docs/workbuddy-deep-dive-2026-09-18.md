# Anti-FOMO × WorkBuddy：面向证据型研究与方案交付的深度对标

**研究快照：2026-09-18　|　重点复核：2026-09-22　|　下一次完整复核期限：2026-10-02　|　报告状态：研究稿，不能替代客户验收或生产 SLA**

2026-09-22 复核了 Quick Start、Buddy App、第三方应用 OAuth/Open API、自动化、Enterprise 版本和计费六个官方页面。它们仍支持本文的核心竞争判断；计费页已更新至 2026-09-21，价格与历史计费示例的口径区别见第 6 节。Enterprise 产品页、Task Bar、Permission Modes 本次抓取超时，保留 09-18 快照，不把抓取失败解释为功能下线。本次不是对下方全部 30 个来源的重新认证。

本次人工页面复核也**不续期机器监测注册表**，不会改变 [来源监测 issue #10](https://github.com/ChrisChen667788/antifomo/issues/10) 的来源状态；机器来源只有按其抓取、digest、复核与审批流程完成后才能更新。

这份报告回答一个实际问题：在招投标、客户方案和竞品监测这些工作里，Anti-FOMO 与腾讯 WorkBuddy 到底各自解决什么问题，哪些能力会形成真实竞争压力，哪些能力可以借鉴，怎样以可回滚、可测量、可审计的方式加入后续迭代。

报告把四类事实分开：

* **官方能力**：腾讯/WorkBuddy/CodeBuddy/WorkBuddy Enterprise 的产品页、文档、开放平台、隐私政策或更新日志明确写出的能力。
* **Anti-FOMO 本地实现**：本 checkout 中可定位到的代码、接口、脚本和测试；它仍然是本地优先开发原型。
* **未实测**：公开页面提到但本报告没有用同一任务、同一输入和同一环境复现的能力。
* **外部验收/生产**：目前没有因为功能已存在、CI 通过或有宣传材料就自动成立。客户签字、独立评测、部署运行和 SLA 仍需单独证据。

## 1. 结论先行

WorkBuddy 是一个已经产品化的**通用桌面 Agent 与企业 Agent 平台**：它把自然语言任务、Plan/Agent/Ask 工作模式、本地文件、模型切换、Skill/Expert/MCP、团队空间、定时任务、手机端遥控和企业席位/积分商业化放进同一套体验。Buddy App 又允许合作伙伴用六个维度定制行业工作台：工作模式、场景胶囊、模型、垂直能力市场、已有系统/MCP 集成，以及对应的首页/应用配置。因此不能把 WorkBuddy 概括成“没有垂直能力”或“只是泛办公工具”。其真实威胁是：它能够把招投标、售前和行业研究包装成低门槛的一句话入口，并借助生态资产快速覆盖场景。

Anti-FOMO 的机会在另一层：把微信/网页信号推进成**可追溯的主张、来源版本、证据覆盖、架构决策、人工修订和审计交接**。截至本报告，Anti-FOMO 在这条证据链上有更多本地工程合同；WorkBuddy 的公开材料没有证明它提供同等粒度的 claim-level citation、来源新鲜度门禁、版本比较或“证据不足保持 HOLD”的研究质量闭环。本句只是公开资料差异判断，不是 WorkBuddy 质量更低的结论，也没有同一基准实测支持。

推荐路线是 **“吸收 WorkBuddy 的入口和执行体验，保留 Anti-FOMO 的证据边界”**：

1. 先把 `Ask → Plan → Execute` 做成研究任务信封；计划必须可审阅、可拒绝、可重放。
2. 先做只读的官方来源/竞品监测 scheduler，再做外部写入连接器。
3. 用已存在的 Skill inventory、垂直包、connector sync、operation evidence 和审计交接，组合出受治理的行业工作台。
4. 以招投标、客户方案、竞品监测三类固定任务做对比实测，分别报告证据覆盖、结果正确性、延迟、失败恢复、成本和人工审阅时间；不发布无定义的“提效百分比”。

## 2. 产品边界与竞争对象

### 2.1 WorkBuddy 的三种东西必须分开

| 名称 | 公开资料中的性质 | 与 Anti-FOMO 对比时的处理 |
| --- | --- | --- |
| **WorkBuddy Desktop/Web/Mobile** | 腾讯 WorkBuddy 的通用职场 Agent 产品；能规划任务、读写授权文件、生成文档/表格/PPT、调用工具和运行自动化 | 与 Anti-FOMO 的用户体验和任务完成面比较；公开营销能力要标 `vendor_claim` |
| **WorkBuddy Enterprise / Managed Agents** | 企业席位、组织与权限、企业模型、连接器、云端 Runtime/Session、企业 Agent 评测与 OpenAPI | 与 Anti-FOMO 的企业治理、托管和商业化路线比较；不把其价格或产品页当成实际 SLA |
| **官方 CodeBuddy CLI / WorkBuddy 兼容 CLI** | CodeBuddy 命令行的交互/无头执行、会话恢复、MCP/Skills/工具参数；Anti-FOMO 现有桥接主要检测并调用这条本地 CLI | 仅说明“兼容/桥接”，不能写成 Anti-FOMO 已接入腾讯托管 WorkBuddy Enterprise |

Anti-FOMO 的 `backend/app/services/workbuddy_adapter.py` 会探测本机 `codebuddy`、CLI 版本、登录状态和可选 gateway；`backend/app/api/workbuddy.py` 提供健康与回调入口；`docs/workbuddy-official-cutover.md` 已明确“本地兼容/CLI bridge 不是官方腾讯托管租户”。当前 webhook 由 schema 限定导出任务类型，但调用 `create_and_execute_task` 前没有人工审批：配置 secret 时校验签名，未配置时返回 `signature_bypassed_no_secret` 并继续；任务后还可向请求/配置的 callback URL 发送结果。因此只能称为“本地导出/CLI 兼容桥”，不能把签名、来源认证或任务类型白名单写成完整的执行授权。2.12.0 负责收敛这一入口及已有 `/api/tasks` 入口。这条边界必须在 README、演示和商业材料中保持。

### 2.2 Anti-FOMO 的现状证据

当前公开状态页将 `2.10.3–2.11.8-development` 标记为本地实现，release promotion 仍 `blocked`。可核验的本地能力包括：

* 来源采集、微信/网页入口、来源新鲜度和竞品监测：`scripts/competitive_monitor.mjs`、`scripts/capture_competitive_evidence.mjs`、采集器和相关 backend service。
* 研究运行和状态转换：`backend/app/services/decision_program/control_room.py`、`backend/app/services/research/*`。
* Claim/证据和方案工作台：`backend/app/services/decision_studio/claim_graph.py`、`backend/app/services/decision_program/document_editor.py`、`backend/app/services/decision_program/verticals.py`。
* 垂直包已含医疗、金融、文旅三个模板，带官方来源注册表、ontology、硬负例、rubric 和需要 100 个任务/30 个专家复核的 benchmark 门槛；这代表本地工程合同，尚不代表真实行业验收。
* Skill 签名、权限、dry-run 和运行回执：`backend/app/services/decision_studio/skills.py`。
* 企业身份、connector sync、ACL snapshot：`backend/app/services/decision_program/enterprise.py`。
* 追加式 operation evidence、幂等 digest、dry-run、rollback rehearsal、gate review、audit handoff：`backend/app/services/product_strategy/operation_evidence_service.py`、`backend/app/api/product_strategy_operations.py`。

这些代码可以支撑下一阶段，但不能把“存在接口”写成“已有可运营的 WorkBuddy 式企业产品”。

## 3. 双向能力对照

| 维度 | Anti-FOMO 当前已实现/可展示 | WorkBuddy 官方公开能力 | 公平判断 |
| --- | --- | --- | --- |
| 入口 | 微信/网页/文件信号进入可恢复研究链路 | 一句话任务、桌面/网页/移动端、微信聊天记录转发 | WorkBuddy 入口和低门槛更强；Anti-FOMO 的微信到证据链更聚焦 |
| 任务形态 | 研究 run、Focus、方案和行动输出；治理证据链可 HOLD，旧导出 webhook 仍会直接执行 | Agent、Plan、Ask；多任务并行；授权本地文件操作 | Anti-FOMO 应吸收 Plan/Ask 的交互，并把旧入口纳入统一授权 |
| 研究证据 | 来源版本、Claim/Evidence、检索诊断、freshness、revision、audit handoff | 官方称支持行业调研和可验收产物；公开资料未核验同等 claim-level ledger | Anti-FOMO 的研究治理是差异化，但未完成独立质量验收 |
| 招投标/方案 | 垂直 evidence packs、架构 readiness、ADR、风险、验证动作和客户问题 | 通过 Buddy App/Expert/Skill/Connector 可配置行业场景，通用产物覆盖强 | WorkBuddy 具备进入垂直场景的能力；Anti-FOMO 将论证血缘作为显式数据合同，实际正确性仍需评测 |
| 垂直能力 | 本地 medical/finance/tourism packs，硬负例与证据等级合同 | Buddy App 六维定制，专家/技能/连接器/场景胶囊/模型组合，支持 MCP Apps | WorkBuddy 是实际竞争威胁，不能写成“没有行业能力”；Anti-FOMO 可做“证据型垂直包”差异 |
| 生态 | 本地 adapter、扩展、小程序和受控 connector 方向 | 腾讯文档、乐享、会议、QQ 邮箱、TAPD、企微/QQ/飞书/钉钉等连接器和开放平台资产 | WorkBuddy 生态宽；Anti-FOMO 应兼容而非重建生态 |
| 团队协作 | Claim Graph、ACL/身份和审阅证据的本地工程合同 | 团队空间、四档权限、按当前用户权限读、评论和 AI 修订建议 | WorkBuddy 的协作 UX 已产品化；Anti-FOMO 可将修订绑定到证据与版本 |
| 自动化 | 竞品来源 monitor 和 run receipt；可做只读定时刷新 | 定时任务、频率/时长/并发限制、企微/小程序通知、失败重试 | WorkBuddy 的无人值守体验领先；Anti-FOMO 先做研究专用 bounded scheduler |
| 移动控制 | 当前没有可宣称的官方移动端控制 | 手机查看、继续、暂停/停止、状态和产物回传 | 这是明确短板；可先做低风险审批/停止，不直接复制文件写入 |
| 模型 | 记录 baseline_hybrid、模型/成本证据和 fallback 约束 | Auto/快速/均衡/极致、自定义 API、Ollama、多个模型和上下文配置 | WorkBuddy 配置面更宽；Anti-FOMO 应记录模型但不承诺模型质量 |
| 安全 | fail-closed、签名 Skill、scope、幂等、digest、审计；发布仍 HOLD | 默认权限/Full Access、安全沙箱、备份、敏感保护、网关、权限确认 | 两者的安全模型不同；不能写“Anti-FOMO 更安全”，要用固定协议测量 |
| 商业化 | MIT 开源核心；企业能力/客户验收未完成 | 个人/企业席位、Credits、共享/专享 VPC、私有化、OpenAPI/生态 | WorkBuddy 商业闭环更成熟；Anti-FOMO 不能宣称独占许可或已产生商业收入 |

## 4. 三个目标场景

### 4.1 招投标项目研究

**Anti-FOMO 适合的问题**：从政府/招标网站、公众号、公告和附件中抽取项目主体、资格条件、时间、采购模块、AI 结合点和证据；把每个判断绑定到来源版本和截止时间；对来源缺失或过期保持 HOLD。

**WorkBuddy 的竞争压力**：WorkBuddy 的桌面 Agent、行业 Buddy App、文档/表格 Skill、连接器和定时任务能够把“读取一批 PDF/Excel、提取字段、生成汇报”做得更低门槛。Buddy App 的场景胶囊可以把“招标文件解析”“竞争格局”“投标材料初稿”放在首页，形成比 Anti-FOMO 更短的首次体验。

**Anti-FOMO 的防守点**：投标结论往往要区分公告、资格预审、候选、中标、已签约和推断角色；单纯生成文档不能证明来源时点和实体关系正确。Anti-FOMO 已有实体/垂直包、source freshness、claim/evidence 和审计回执方向，可把“可追溯、不越界”产品化。

**可比实测协议 T1**：

1. 固定同一批 20 个公开招标项目，冻结 URL、抓取日、附件 hash 和任务描述；不使用客户隐私数据。
2. 为每个项目定义 30 个字段：采购阶段、主体、预算、时间、AI 模块、资格条件、原文定位、证据时效和不确定性。
3. Anti-FOMO 与 WorkBuddy 均使用相同文件包和同一模型预算；WorkBuddy 只能使用已授权本地目录与公开连接器，Anti-FOMO 使用 `baseline_hybrid`。
4. 确定性评分：字段精确率/召回率、来源定位命中率、过期来源拒答率、重复实体率、hash/结构完整性。
5. 人工盲评：两名独立评审分别给证据充分性、投标可用性和错误风险评分；记录人工修订分钟数。
6. 稳定性：每组重复 3 次，记录 p50/p95、失败/重试、输出完整率、成本和可重放率。该协议产生 synthetic benchmark，不是客户投标成功率。

### 4.2 客户解决方案

**Anti-FOMO 适合的问题**：把行业/客户场景、约束、目标、架构层、NFR、风险、ADR、验证动作和下次会议议程绑定到 Claim Graph 与证据包。

**WorkBuddy 的竞争压力**：它可用 Expert/Skill/Buddy App 预置行业角色，用自然语言处理文件并生成 PPT、DOCX、表格和网页；企业版还能统一模型、连接器、身份、Session 和 Agent 评测。这会把“第一次方案草稿”成本压得很低。

**Anti-FOMO 的防守点**：方案价值不止是写得像 PPT，而是要求客户场景和架构决策可复核、假设和缺口显式、来源/版本和人工接受记录可追溯。当前 `decision_program/commercial.py` 已将 Pilot 证据、Office roundtrip、audit export 和 customer signoff 分开，并在缺证据时阻断 signoff；这一边界必须保持。

**可比实测协议 T2**：

1. 选 10 个脱敏客户场景，每个固定需求说明、现状架构、NFR、预算区间和允许引用的来源包。
2. 两个产品分别输出：一页 executive brief、四层架构图、ADR、风险登记、验证计划、10 页 PPT 和引用清单。
3. 确定性评分：必填章节、字段/版本一致性、架构图节点与正文一致、引用可打开、Office 文件可渲染；对同一已保存产物的规范化 manifest 重算 digest 应一致。重新请求模型不是同一产物，Office 容器时间戳等非语义字段须单独规范化，不能要求随机生成文件的原始字节恒定。
4. 独立架构评审：技术适配、业务可行性、风险可见性、证据完整性、返工时间；评审者不知道产物来自哪一方。
5. 生产/客户接受不从实验分数推导；必须另取带签字的 Pilot artifact，才可改变 Anti-FOMO release gate。

### 4.3 竞品监测

**Anti-FOMO 适合的问题**：登记官方来源、抓取、正文/hash、内容变化、来源新鲜度、人工复核、路线影响和回滚；不因某次抓取失败就写成产品已变更。

**WorkBuddy 的竞争压力**：定时任务、联网浏览、Skill、连接器、手机通知和云端托管可快速生成日报/周报。Buddy App 还可把“竞品简报”作为场景胶囊推给非技术用户。

**Anti-FOMO 的防守点**：竞品监测最怕把“页面改版”“来源失效”“厂商营销说法”“独立测评”混成事实。Anti-FOMO 的 monitor 运行已有全量来源、失败/过期和 digest 记录，适合把通知与证据升级拆开。

**可比实测协议 T3**：

1. 固定 20 个官方产品/定价/更新日志源，设置同一抓取时间、user-agent、超时和重试上限；所有原始页面保存 hash，不能用实时页面回填历史。
2. 运行 14 天，每日两次；注入 5 类故障：404、超时、内容重复、页面局部变化、日期倒退。
3. 比较：成功率、陈旧检测召回率、误报率、变化定位准确率、从失败恢复时间、重复通知率、每次运行成本。
4. 人工复核 100 条变化，标签为“功能事实/价格事实/营销主张/版本变更/无法判断”；只有官方事实通过门禁才进入路线图。
5. WorkBuddy 的联网/自动化结果若无可导出的原始来源和时间戳，只计为候选摘要，不计为可审计证据；这是协议约束，不是对其功能的负面断言。

## 5. WorkBuddy 借鉴项与 Anti-FOMO 落地映射

| 借鉴模块 | Anti-FOMO 对应代码/数据 | 建议动作 | 决策 |
| --- | --- | --- | --- |
| Agent/Plan/Ask | `decision_program/control_room.py` 的 run 状态；`product_strategy/operation_evidence_service.py` 的 proposal/dry-run | 新增研究任务信封：scope、source set、freshness budget、write targets、cost/timeout、审批 digest | **build** |
| Buddy App 场景胶囊 | `decision_program/verticals.py` 的垂直包；`decision_studio/skills.py` 的 Skill | 把招投标/客户方案/竞品监测做成 2–4 个模式、每个 5 个场景入口；先导出 JSON 本地预览 | **build** |
| WorkBuddy Expert/Skill/Connector | `decision_program/enterprise.py` connector sync；`operation_evidence_service.py` skill inventory；`skills.py` 签名/权限 | 统一 manifest：capability、read/write、scope、credential_ref、owner、version、撤销和审计回执 | **build** |
| 团队空间和 AI 修订建议 | `claim_graph.py`、artifact acceptance、human acceptance | claim/章节级 suggestion diff；accept/reject 后落正文，保留 revision digest、评论线程和角色 | **build** |
| 自动化任务 | `scripts/competitive_monitor.mjs`、monitor API、operation evidence | 只读 scheduler：时区、并发、heartbeat、pause/cancel、bounded retry、resume-from-receipt、通知不阻塞任务 | **build** |
| Runtime/Session 状态 | agent operations 状态、run checkpoints、audit handoff | 统一 `queued/running/waiting_input/succeeded/stopped/failed/stale`，外部写操作强制幂等 | **build** |
| 多端远程查看/停止 | 当前前端状态接口和 WorkBuddy webhook 健康桥 | 先实现移动视口上的状态/审批/停止；设备签名绑定，禁止移动端直接高危写入 | **build** |
| 模型 Fast/Balanced/Deep | 现有 `baseline_hybrid`、model/cost ledger、performance evidence | 每次 run 固定 provider/model/context/latency/cost/fallback；只有评测通过才改变默认路由 | **build** |
| OpenAPI/OAuth 连接器 | `enterprise.py` 已有 issuer、role mapping、ACL snapshot、secret 禁止落 payload | 兼容 OAuth 2.1/MCP 只读范围；短生命周期 token、scope/撤销/限流；不把 WorkBuddy token 存入本地证据 | **integrate** |
| WorkBuddy 官方 CLI | `workbuddy_adapter.py`、`api/workbuddy.py`、`workbuddy-official-cutover.md` | 保持 CLI bridge 与 Desktop/Enterprise 命名分离；增加 execution receipt 和 fail-closed approval | **integrate** |
| 云端托管 Agent / 私有化 | Anti-FOMO 当前无可核验生产租户与 SLA | 先做本地沙箱和受控 Pilot；完成 RTO/RPO、渗透、客户验收后再决定托管 | **defer** |
| WorkBuddy Credits 计费复制 | Anti-FOMO 是 MIT 开源项目，尚无授权/用量闭环 | 记录 cost ledger、行业包和企业服务报价假设；不复制腾讯计费或宣称独占商业许可 | **defer** |
| 通用 PPT/图片/视频生成 | 现有 Office/visual receipt 仅证明文件/渲染回执 | 先接入已有编译器与人工接受；创意生成作为独立 Skill，不进入证据默认链路 | **defer** |

### 5.1 研究工作包与版本归属

后续十个发布版本统一为 **2.12.0–2.21.0**，完整 API、迁移、验收预算和回滚合同只由 [受控执行集成计划](./workbuddy-integration-plan-2026-09-18.md) 维护。下表 `R01–R10` 是本报告的研究工作包 ID，不是另一个版本系列，也不独立承诺交付时间。

| 研究工作包 | 对应工程版本 | 需要提交的研究证据 |
| --- | --- | --- |
| R01 任务与授权 | 2.12.0–2.13.0 | 信封字段、不可变计划、所有旧入口的授权负例 |
| R02 招投标场景 | 2.20.0 | T1 的 20 项目 × 30 字段合同、实体/阶段负例和独立审阅 |
| R03 连接器授权 | 2.15.0 | manifest、scope、secret reference、撤销/过期测试 |
| R04 定时与恢复 | 2.14.0、2.19.0 | heartbeat、bounded retry、重启恢复、外写 unknown 处置 |
| R05 多端状态 | 2.18.0 | 设备绑定、断网重连、重复命令、暂停/停止回执 |
| R06 协同修订 | 2.16.0–2.17.0 | claim/章节 suggestion diff、接受/拒绝、规范化 digest |
| R07 能力兼容 | 2.15.0 | Skill/Expert 签名、许可证、版本和权限兼容矩阵 |
| R08 竞品监测 | 2.14.0、2.19.0 | T3 的 20 源 × 14 日运行、故障注入与变化分类 |
| R09 固定评测 | 2.20.0 | T1/T2/T3 分域报告、延迟/成本/返工时间；不合成跨域总分 |
| R10 商业化证据 | 2.21.0 | 用量对账、退出包、独立人工与客户回执分列 |

这些是待完成的研究/验收材料。阈值均为目标，必须随样本和环境报告实测值；未通过人工、客户或生产门禁时，不得提升 release status。

## 6. 商业化与价值测量

2026-09-22 复核的[腾讯云版本说明](https://cloud.tencent.com/document/product/1831/134332)（页面更新于 09-16）列出旗舰版共享 VPC 1 席起、198 元/人/月；专享版专属 VPC 100 席起、316 元/人/月；私有化企业版价格需咨询。[计费说明](https://cloud.tencent.com/document/product/1831/134334)（页面更新于 09-21）仍写明每席每月 2,000 Credits、预付费及成员额度控制。该页同时保留了按 2025 年购买日期计算的 78 元历史示例，不能当作当前旗舰版报价。不同 edition、地区、时间和合同不能混写；个人版价格也不能替代企业版价格。

Anti-FOMO 当前仓库为 MIT License。MIT 允许使用、修改和再分发，但不构成独占许可，也不证明任何行业包、模型、来源内容或第三方连接器的授权。商业化建议分三层：

1. **开源核心**：本地采集、研究、证据账本、基础 UI、测试和可复现 benchmark。
2. **企业服务/私有部署候选**：行业证据包定制、来源注册表治理、部署、培训、Pilot 评估和审计交接；只有签约后才记为收入/客户项目。
3. **受控托管候选**：在身份、密钥、租户隔离、RTO/RPO、审计、成本和客户验收成立后，再评估托管；当前不是生产承诺。

价值测量必须从任务级事实开始：

* `time_to_first_grounded_artifact`：从固定输入到第一份可引用产物的时间。
* `evidence_coverage`：关键字段中有可打开来源、版本和定位的比例。
* `stale_source_block_rate`：过期/撤销来源被正确 HOLD 的比例。
* `human_review_minutes` 与 `revision_count`：人真正花了多少时间、返工多少次。
* `artifact_replay_success`、`connector_error_rate`、`p95_latency`、`cost_per_run`。
* 招投标进一步测“字段精确率/召回率、实体误识别率”；客户方案测“架构评审通过率/返工时间”；竞品监测测“变化定位准确率/误报率”。

这些是评测设计，不是已有客户结果。营销材料只有在固定样本、版本、日期和可下载证据包同时存在时，才可以引用数值。

## 7. 营销与“活人感”设计

不要模仿 WorkBuddy 的“超级个体”或把通用办公效率数字搬到 Anti-FOMO。Anti-FOMO 的镜头应让人看到一个真实判断如何被推进：

1. **信号进入**：微信收藏、网页和 PDF 以不同来源标签进入队列；不隐藏失败和缺失。
2. **人提出问题**：显示角色、截止时间、研究范围和“我需要回答客户哪一个问题”。
3. **证据被钉住**：Claim 展开原文、来源时间、revision digest、检索命中和 reviewer comment。
4. **不确定性停下来**：一个缺证据字段保持 `HOLD`，显示下一步补证动作，而不是生成绿色通过。
5. **共同修改**：显示 reviewer 的划词评论、AI suggestion、接受/拒绝和正文 hash 变化。
6. **形成方案**：架构蓝图、ADR、风险、验证动作和下次会议议程一一从证据节点连出。
7. **留下回执**：导出 Markdown/Office/audit handoff，展示谁在何时接受了什么版本。

后续拟拍摄的 30 秒实机演示分镜（`planned`）：`0–4s 信号碎片 → 4–9s 来源健康 → 9–15s claim/证据展开 → 15–20s HOLD 与补证 → 20–26s 架构/行动卡 → 26–30s review receipt`。这不是本次交付的 15 秒无声历史 UI 蒙太奇；两者区别与现有素材见 [营销物料方案](./marketing-overhaul-2026-09.md)。画面中的队列数、耗时、覆盖率必须读取真实本地样本或标注 synthetic/demo；不能伪造客户头像、签字、DAU 或生产吞吐。

两张主图应固定为：

* **架构图**：输入适配器 → 可恢复队列 → 研究编排 → Claim/Evidence → 对比/垂直包 → 架构工作台 → 人工评审 → 交付/审计；治理层横跨每一层。
* **状态图**：`queued → running → waiting_review → hold/approved → succeeded/stopped/failed → replay/revoked`；任何外部写操作都经过 scope、预算、审批和 receipt。

## 8. 官方来源注册表

以下注册表保留 **2026-09-18 研究快照**；S03、S05、S06、S13、S15、S19 于 **2026-09-22** 复核。完整来源复核期限仍为 **2026-10-02**，未随局部复核延后。超过期限后应重新抓取并记录内容 digest；本 Markdown 来源表还不是具备原始页面、digest 和自动过期执行能力的机器证据账本。`A`=腾讯官方产品/文档/开放平台/隐私/更新日志，`B`=腾讯官方投资者/研究材料，`C`=WorkBuddy 官方开源 benchmark/论文（方法证据，不代表生产 SLA）。

| ID | 官方来源（URL） | 核验事实与边界 | 地区/版本限制 | 等级 |
| --- | --- | --- | --- | --- |
| S01 | [腾讯云 WorkBuddy 产品页](https://cloud.tencent.com.cn/product/workbuddy) | 全场景办公、自然语言、自主规划、本地文件、多模态、专家、云端任务、多 Agent | 中国站；产品页能力声明 | A |
| S02 | [WorkBuddy 产品介绍](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Product-Guide) | 定位为职场 AI 桌面工作台；模型切换、MCP、Skill、高危指令拦截 | WorkBuddy 文档版本 | A |
| S03 | [WorkBuddy Quick Start](https://www.workbuddy.ai/docs/workbuddy/Quickstart) | 一句话任务、自治执行、并行、本地文件、可验收产物 | 国际站；PC/Web 功能可能不同 | A |
| S04 | [WorkBuddy Enterprise 产品](https://cloud.tencent.com/product/workbuddy-enterprise) | 企业研发/办公 Agent、Managed Agents、统一身份、安全治理、OpenAPI | 企业版，非个人版 | A |
| S05 | [Enterprise 版本说明](https://cloud.tencent.com/document/product/1831/134332) | 共享/专享/私有化 edition、席位门槛、企业生态权益 | 2026-09-16 更新；价格随合同/地区变化 | A |
| S06 | [Enterprise 计费说明](https://cloud.tencent.com/document/product/1831/134334) | 预付费、Credits、加量包、成员限额、过期抵扣 | 09-22 复核，页面更新至 09-21；历史价格示例不能替代当前版本报价 | A |
| S07 | [Managed Agents 快速开始](https://cloud.tencent.cn/document/product/1831/134527) | Agent 配置、Manifest、Skill/Expert/MCP/Connector、Test Run、渠道、Runtime/Session、评测 | WorkBuddy Enterprise WMA | A |
| S08 | [连接器文档](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector) | QQ 邮箱、腾讯文档、乐享、会议、TAPD；MCP/CLI；授权/撤销/不主动抓取 | 连接器可用性和权限依赖账号 | A |
| S09 | [团队多 Agent 协作](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Library/Collaboration) | 团队空间、四档权限、按用户权限读取、评论、AI 修订建议、接受后写正文 | 资料库功能；未测 Anti-FOMO 兼容性 | A |
| S10 | [模型配置](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model) | 快速/均衡/极致、自定义模型、Ollama、上下文/Max 模式、API Key 本地保存 | 模型列表/地区/套餐会变；不代表质量 SLA | A |
| S11 | [新建任务栏](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Task-Bar) | Agent/Plan/Ask、工作空间、Skill、拖拽附件、微信记录、并行任务 | Desktop 文档；不同端功能可能不同 | A |
| S12 | [默认权限与安全沙箱](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Permission-Modes) | 默认权限/Full Access、文件/命令/网络规则、备份、敏感保护、删除保护 | 客户端设置；不是独立安全认证 | A |
| S13 | [自动化任务](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Automation-Guide) | 定时 prompt、工作空间、模型/技能、频率/时长/并发、企微/小程序通知、重试建议 | 本地自动化/受账号与设备影响 | A |
| S14 | [多端协同](https://www.workbuddy.cn/docs/workbuddyapp/features/Multidevice) | 手机查看、续聊、停止、状态、产物回传和导出；加密中继/设备绑定 | Mobile + Desktop；联网和锁屏运行前提 | A |
| S15 | [Buddy App 文档](https://open.workbuddy.cn/docs/buddy-app) | 垂直 AI Harness；工作模式、场景胶囊、模型、能力市场、既有 MCP、预览/审核/发布 | 开放平台；部分账号可能灰度 | A |
| S16 | [Buddy App 六维设计](https://open.workbuddy.cn/en/docs/buddy-app) | 六维定制和五模块配置；至少 5 场景、2–4 模式建议 | 英文开放平台，地区/审核依赖平台 | A |
| S17 | [WorkBuddy 更新日志](https://www.workbuddy.cn/docs/workbuddy/Changelog) | 5.5.x 修复重试、状态、MCP、中断、切换、并行等；新增行业 Buddy App | 版本变动快；修复记录不是 SLA | A |
| S18 | [开放平台](https://open.workbuddy.cn/) | Buddy、Expert、Skill、Connector、Hardware；生态规模/伙伴数是平台宣传 | 官方营销数字需注明日期和口径 | A |
| S19 | [第三方应用 OAuth/Open API](https://open.workbuddy.cn/docs/third-party-app) | OAuth 2.1、Scope、短期 access/refresh token、云端任务/产物/本地助理 API | 需审核、用户显式授权；scope 受限 | A |
| S20 | [Skill 开发文档](https://open.workbuddy.cn/docs/skill) | Skill 包基础结构和上传解析 | 开放平台资产格式；不证明 Anti-FOMO 可直接安装 | A |
| S21 | [Expert 开发文档](https://open.workbuddy.cn/docs/expert) | Expert manifest、connector 依赖、token 不得硬编码、行业分类 | 开放平台；审核与依赖状态影响可用性 | A |
| S22 | [CodeBuddy 无头模式](https://www.codebuddy.cn/docs/cli/headless) | `-p`、JSON/stream、定时工具；授权参数 `-y` 风险边界 | CodeBuddy CLI；不是 WorkBuddy Enterprise | A |
| S23 | [CodeBuddy CLI 快速入门](https://www.codebuddy.cn/docs/cli/quickstart) | 安装、登录站点、Node/OS、单次命令和工具授权 | CLI 版本/站点/地区不同 | A |
| S24 | [CodeBuddy CLI 参考](https://www.codebuddy.cn/docs/cli/cli-reference) | session、MCP、strict config、no-session、工具白名单 | CLI 参考中部分功能可能预留 | A |
| S25 | [WorkBuddy 国际隐私政策](https://www.workbuddy.ai/document/privacy-policy) | 输入/输出、第三方 LLM/Skill/MCP、训练开关、跨境和第三方处理边界 | 国际服务；不适用于 Enterprise | A |
| S26 | [腾讯 WorkBuddy Bench GitHub](https://github.com/Tencent/workbuddy-bench) | Code/Web/Office/Security 任务目录、Docker、轨迹/产物/测试/效率 | benchmark harness，不等于 WorkBuddy 线上指标 | C |
| S27 | [WorkBuddy Bench 论文](https://arxiv.org/abs/2607.20911) | 四域分别计分、公开可审计、Office 当前文本优先且不覆盖 OCR/GUI | 论文版本/模型和 harness 固定 | C |
| S28 | [腾讯投资者材料（2026-05）](https://static.www.tencent.com/uploads/2026/05/13/e048dfed72bc718f7986a83f23c8e294.pdf) | WorkBuddy/CodeBuddy 用户留存快照等厂商披露 | dated investor disclosure；非当前 SLA | B |
| S29 | [腾讯投资者材料（2026-06）](https://static.www.tencent.com/uploads/2026/06/17/8bc964b385a06fabaecb8b6ce0bffff4.pdf) | 另一日期/口径的活跃与付费留存快照 | 与 S28 不应合并成单一长期数字 | B |
| S30 | [腾讯云 WorkBuddy TokenHub 指引](https://intl.cloud.tencent.com/zh/document/product/1300/80640) | WorkBuddy 可接 TokenHub、自定义模型/API、QQ/企微适配 | 国际站/TokenHub；按模型和账号计费 | A |

注册表的 `verified_at`、`expires_at`、`source_class`、`claim_digest` 应在后续脚本中落成机器可读记录。失效日不是“来源必然失效”，而是本项目要求重新核验的时间边界。

## 9. 评审与发布门禁

本报告本身只是研究文档，不能将 WorkBuddy 的官方能力转化为 Anti-FOMO 的实现承诺。每个后续模块合并前至少提供：

* 代码路径、迁移和 API schema；
* 单元/集成/并发/故障恢复测试；
* digest、幂等键、权限 scope 和失败状态；
* 可重放的本地 artifact，明确 demo/synthetic/vendor/human/customer/production 标签；
* 对外营销截图、GIF、架构图和流程图的来源说明；
* 若涉及外部服务，单独登记授权、地区、隐私、费用和撤销路径。

任何“比 WorkBuddy 更安全”“质量更高”“节省 X%”“已有企业使用”“支持腾讯官方企业版”等句子，在没有同一协议和可审计证据前都不得进入 README、官网、PR 或销售材料。

## 10. 一页决策

Anti-FOMO 应把 WorkBuddy 官方资料展示的产品方法吸收进证据工作流：**低门槛场景入口、先计划后执行、Skill/Connector/Expert 组合、团队审阅、状态可见、定时和跨设备控制**；同时把 Anti-FOMO 的差异化方向讲清楚：**来源有版本、主张有证据、缺口会 HOLD、架构有血缘、人工接受有回执、结果可以重放和审计**。这些差异需要 T1/T2/T3 的同任务验证，不能称为不可替代或已经证明优于 WorkBuddy。

这条路线既承认 WorkBuddy 在垂直 Harness、生态和商业化上的现实优势，也让 Anti-FOMO 在自己的垂直领域——招投标情报、客户方案论证和竞品证据监测——建立可测量、可落地、可回滚的差异化。
