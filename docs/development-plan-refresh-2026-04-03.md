# Anti-FOMO 当前版本回顾与开发计划

更新时间：2026-04-21

## 1. 当前版本结论

- 当前仓库版本已更新到 `0.2.0`，并开始进入 RAG 检索质量工程阶段。
- 以 `2026-04-03` 为基线，项目已通过一轮完整验证：
  - `npm run check` 通过
  - Next.js 生产构建通过
  - 后端 `77` 个测试全部通过
- 最近一轮实质开发集中在 `2026-03-28` 到 `2026-04-02`，重点不再只是 Feed / Focus / Session Summary，而是已经进入：
  - 研究中心持久化
  - 专题版本化与刷新
  - Watchlist 自动化
  - Daily Brief
  - 多格式采集
  - Knowledge Intelligence
  - 微信采集链路质量诊断

结论：当前阶段应把项目定义为“研究型信息工作台 + 自动化采集与追踪系统”，而不是继续按最初 MVP 思路排计划。

## 2. 需求演化回顾

从仓库里的 README、方案文档、迁移和测试来看，需求已经经历了这几轮变化：

1. 初始 MVP
   - Inbox / Feed / Item Detail / Focus / Session Summary / Saved
2. 微信公众号导入与 30 篇实测
   - 浏览器插件
   - URL 批量导入
   - 微信文章链路验证
3. 全天候采集
   - 电脑端采集器
   - URL-first 主链路
   - OCR fallback
   - 微信 PC Agent 运维
4. 研究中心升级
   - 深度研究报告
   - Compare Workspace
   - Saved Views
   - Tracking Topics
   - 版本历史与 Diff
5. 自动化与经营化
   - Watchlists
   - Daily Brief
   - 扩展导出任务
   - Knowledge Intelligence / Commercial Hub
6. 多格式输入
   - RSS
   - Newsletter
   - File
   - YouTube transcript

结论：现在的主矛盾已经不是“功能够不够多”，而是“研究质量、版本化工作流、自动化运维、商业输出是否足够稳定和专业”。

## 3. 当前已落地能力

### 3.1 采集与入库

- URL / text / plugin / OCR / URL ingest / plugin ingest / process pending 已具备。
- 微信采集链路已形成 `URL-first -> share/copy -> historical resolve -> OCR fallback` 的正式方向。
- Collector 已支持：
  - source 管理
  - failed retry
  - pending flush
  - daily summary
  - daemon status
  - wechat agent status
- 多格式采集已进入代码与测试范围。

### 3.2 研究中心

- 已有研究报告生成、研究工作台、专题详情页、对比矩阵。
- 已有 Saved Views、Tracking Topics、专题刷新、版本持久化。
- 已有基础版：
  - source diagnostics
  - evidence density / source quality
  - Top 3 排名拆解
  - 字段级 diff
  - 历史版本对照

### 3.3 自动化与输出

- Watchlist 模型、变更事件、手动刷新、due 计算、自动化状态已具备。
- Daily Brief、扩展导出任务、Watchlist Digest 已进入后端测试。
- WorkBuddy webhook 和导出任务链路已具备基础能力。

### 3.4 知识与商业化

- Knowledge entry、merge、accounts workspace、commercial hub 已进入 Web / 小程序代码。
- Knowledge intelligence 与专题报告元数据映射已落地。

## 4. 对旧方案的重估

### 4.1 已经完成或已有基础版，不应再按“从零开始”排期

- URL-first 采集主路径
- 官方源优先与不足时扩搜
- 实体与联系方式过滤增强
- Compare Workspace
- Tracking Topic 持久化
- 历史版本基础对照
- Source diagnostics 与 route quality

### 4.2 已经部分完成，但需要专业化收口

- 字段级 Diff
- 版本工作台体验
- 证据强度与可信度展示
- Watchlist 自动化运维
- Daily Brief 与 Watchlist / 研究报告联动
- Web / 小程序 / 插件三端一致性

### 4.3 仍是接下来必须补强的核心缺口

- 窄主题查询下官方源命中率仍不稳定
- section 级证据配额和置信度解释仍偏基础
- Compare Workspace 缺正式导出与证据附录
- Watchlist 缺统一的计划任务、失败诊断、告警闭环
- Knowledge Intelligence 与 Commercial Hub 还没有完全变成高频工作入口
- 工程面仍有 `17` 个 lint warning，说明代码收口还不彻底

## 5. 更新后的开发总目标

未来一轮不再追求“继续堆页面”，而是围绕四个目标推进：

1. 提高研究结果可信度
2. 打磨版本化研究工作流
3. 完成自动化追踪与运维闭环
4. 把研究结果真正转成经营动作和输出物

## 6. 更新后的开发计划

## Phase 0：基线收口与发布稳定性

目标：先把当前版本固化成可持续迭代的稳定基线。

范围：

- 清理现有 lint warnings
- 修复 React Hook 依赖告警和未使用变量
- 补齐 README 与文档中的版本说明，避免仍按旧 MVP 理解系统
- 固化一组最小回归命令：
  - `npm run check`
  - `npm run demo:smoke`
  - `npm run demo:simulate`

验收：

- `npm run check` 零错误，warning 尽量清零
- 文档明确“当前系统不是早期 MVP”

## Phase 1：研究质量升级

目标：优先解决“能用”到“可信”的差距。

范围：

- 强化窄主题检索的 query decomposition
- 增强 region / industry / buyer / company scope 过滤
- 强化官方源补源策略与 corrective retrieval
- 补强联系方式、预算、组织入口、项目阶段抽取
- 将 `evidence_density / source_quality / confidence_tone / contradiction` 统一前台可视化
- 为 section 增加更清晰的证据不足说明

验收：

- 窄主题查询下官方源占比更稳定
- 低证据 section 能明确给出“为什么不够”和“下一步补什么”
- 研报不再只输出结论，还能输出证据边界

## Phase 2：版本化研究工作台

目标：把已有的“专题刷新 + 历史版本 + Diff”升级为真正可工作的研究中心。

范围：

- 强化专题页版本工作台
- 完善 side-by-side version review
- 完善字段级 diff 的新增 / 减少 / 改写展示
- 增加 compare workspace 正式导出
- 导出内容补齐 evidence appendix
- 统一生成页、历史页、专题页、Session Summary 的研报结构

验收：

- 任一 Tracking Topic 都能直接查看最近版本、基线版本、字段变化
- Compare Workspace 可导出给老板 / 销售 / 项目推进使用

## Phase 3：Watchlist 与运维自动化

目标：把“手动刷新专题”升级成“可持续运行的观察系统”。

范围：

- 建立统一的 watchlist scheduler / run-due 闭环
- 补齐失败诊断、重试、最近一次刷新说明
- 打通 collector / wechat agent / watchlist 的统一状态视图
- Daily Brief 聚合：
  - 高价值内容
  - watchlist changes
  - 风险项
  - 建议动作
- 形成日报、摘要、提醒三层输出

验收：

- Watchlist 能按计划自动刷新
- 失败原因可见、可重试、可追踪
- Daily Brief 真正成为每天打开系统后的第一屏摘要

## Phase 4：Knowledge Intelligence 与经营化输出

目标：让研究结果直接服务销售、老板汇报和客户推进。

范围：

- 补强 account workspace / commercial hub 的可用性
- 把 research report 映射成：
  - exec brief
  - sales brief
  - outreach draft
  - watchlist digest
- 强化 why now、budget probability、stakeholder map、entry window 等经营字段
- 打通研究报告、知识卡片、动作卡三者的跳转关系

验收：

- 一份研究报告能稳定导出成至少 3 类经营材料
- Knowledge 页面不只是“信息存储”，而是“经营推进入口”

## Phase 5：多端一致性与角色分工

目标：明确三端职责，避免重复建设。

建议分工：

- Web：
  - 主工作台
  - 深度研究
  - 版本对照
  - 导出
- Miniapp：
  - 快速查看
  - 采集补录
  - 运维状态
  - Daily Brief
- Browser Extension：
  - 极速入库
  - 当前页面一键送入

验收：

- 同一能力不再在三端各自长成不同交互
- 用户能明确知道“该在哪一端做什么”

## 6.1 RAG 检索质量工程补充（2026-04-21）

基于对本地资料《大模型应用开发 RAG实战课》的系统研读，新增一条横向工程主线：

- `RAG 检索质量工程`

该主线不替代现有 `Phase 1` 和 `Phase 4`，而是作为它们的底层质量工程补充，重点解决：

- 研报 follow-up 仍偏 prompt 拼接，缺少增量检索与差异证据
- 知识库仍缺真正的 chunk-level 检索与索引层
- 检索后处理仍偏启发式，缺少可插拔 reranker 和上下文压缩
- 质量优化尚未形成离线评估与 A/B 基线

正式补充计划见：

- `docs/rag-practice-book-upgrade-plan-2026-04-21.md`

纳入方式：

1. `Phase 1A`
   - 检索前处理与 research retrieval index
2. `Phase 1B`
   - 检索后处理、章节级生成、可信度前台化
3. `Phase 1C`
   - 评估、缓存、重建与系统优化

建议执行顺序：

- 先完成 `Phase 0`
- 再优先执行 `Phase 1A`
- 然后推进 `Phase 1B`
- 最后补 `Phase 1C`

## 7. 推荐优先级

推荐按下面顺序推进，而不是平均铺开：

1. `Phase 0` 基线收口
2. `Phase 1A` 检索前处理与索引层
3. `Phase 1B` 检索后处理与章节生成
4. `Phase 1C` 评估与系统优化
5. `Phase 2` 版本化研究工作台
6. `Phase 3` Watchlist 与运维自动化
7. `Phase 4` Knowledge Intelligence 与经营化输出
8. `Phase 5` 多端一致性

其中真正的核心主线只有三条：

- 研究质量
- 版本化工作流
- 自动化闭环

## 8. 不建议继续投入的方向

以下方向不应继续作为主计划推进：

- 重新做一轮早期 MVP 页面堆叠
- 把 OCR 当主路径
- 幻想式“直接读取个人微信订阅流 API”
- 付费墙、登录墙、验证码绕过
- 在没有统一信息架构前继续扩更多零散入口

## 9. 本轮执行建议

如果只开一轮短迭代，建议直接这样切：

1. 第一周
   - 完成 Phase 0
   - 启动 Phase 1A 中的检索前处理与 research retrieval index 最小版本
2. 第二周
   - 推进 Phase 1B 中的检索后处理、章节级生成与可信度前台化
3. 第三周
   - 补 Phase 1C 的评估基线，并衔接 Phase 2 / Phase 3 的版本化与自动化能力

这样做的原因很明确：

- 先稳住当前版本
- 再补检索质量工程
- 最后把自动化闭环做起来

这比继续分散做新页面更有效。
