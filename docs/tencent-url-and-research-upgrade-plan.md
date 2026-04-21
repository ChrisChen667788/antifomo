# 腾讯官方 URL 获取方案与研报质量升级方案

更新时间：2026-03-26

## 1. 结论摘要

### 1.1 腾讯官方是否存在“直接读取个人微信公众号模块文章 URL”的更优解

当前结论：**没有查到腾讯官方支持的、可直接枚举个人微信“公众号模块”文章 URL 的能力。**

已确认的官方能力边界：

- `WorkBuddy 微信客服号集成`
  - 能力：在微信里给电脑上的 WorkBuddy 发送任务，并接收执行进度与结果。
  - 不包含：读取个人微信“公众号模块”订阅流、枚举每篇公众号文章 URL。
- `WorkBuddy 微信 ClawBot 集成`
  - 能力：和微信客服号集成功能相同，本质上仍是微信侧任务入口。
  - 不包含：个人公众号历史推文列表抓取能力。
- `CodeBuddy Remote Control / Gateway`
  - 能力：远程访问本地 Agent 会话和 Web UI。
  - 不包含：微信内容 API。
- `微信服务号/公众号素材管理 API`
  - 能力：管理**你自己公众号**的永久素材、图文素材等。
  - 不包含：读取“我个人微信里关注的其他公众号”的历史文章 URL。
- `企业微信会话内容/存档相关能力`
  - 能力：企业内部或企业客户联系相关会话内容能力。
  - 不包含：个人微信“公众号模块”订阅流。

所以，**腾讯官方路线里没有比当前方案更优的“个人公众号 URL 枚举 API”**。

### 1.2 当前最优实现路径

既然没有官方直连能力，下一步的最优解仍然是：

1. `WorkBuddy` 继续做控制/编排通道。
2. 微信公众号采集器继续做 `URL-first` 主路径。
3. 主路径顺序固定为：
   - 直接浏览器 URL
   - 微信文章页分享/复制链接
   - 浏览器打开后读取真实 URL
   - 历史真链恢复
   - OCR 兜底
4. `OCR` 保留为最后一道 fallback，而不是主路径。

### 1.3 研报质量怎么提

当前研报质量问题，不是只靠“换一个更强模型”就能解决，核心在于：

- 检索范围和主题收敛不稳
- 实体抽取和公司归一化不够强
- 证据质量缺乏分层和交叉验证
- 没有显式的多专家分析和知识图谱层
- 证据不足时 fallback 仍然太空

可行方案是：**查询规划 + 多源检索 + 证据分层 + 图谱记忆 + 专家分析器 + 交叉验证 + 强 fallback 输出**。

---

## 2. 腾讯官方能力矩阵

| 官方能力 | 能做什么 | 不能做什么 | 对 Anti-FOMO 的意义 |
| --- | --- | --- | --- |
| WorkBuddy 微信客服号集成 | 在微信中给本地 WorkBuddy 发任务、收结果 | 不能读取个人公众号模块历史文章 URL | 适合做控制通道 |
| WorkBuddy 微信 ClawBot 集成 | 同上，另一种绑定通道 | 不能读取个人公众号订阅流 | 适合做控制通道 |
| CodeBuddy Remote Control | 远程访问本地 Agent/Gateway/Web UI | 不是微信内容接口 | 适合做远程编排/运维 |
| 微信服务号素材管理 API | 获取自己服务号的永久素材、图文素材 | 不能读取个人订阅的第三方公众号文章 | 仅适合“自有公众号资产” |
| 企业微信会话内容能力 | 企业内部/客户联系相关会话内容能力 | 不是个人微信公众号阅读流 | 适合企业场景，不适合个人公众号流 |

### 工程判断

这不是“我们还没找到文档”，而是官方能力的定位本身不同：

- `WorkBuddy/CodeBuddy` 是任务执行与远程控制产品。
- `微信服务号 API` 是公众号运营接口。
- `企业微信 API` 是企业通信接口。

这些都不等于“个人微信订阅流抓取接口”。

因此，下一步不应继续寻找“官方直接获取 URL”的不存在能力，而应继续把自建 `URL-first` 采集器做稳。

---

## 3. URL-first 采集器正式方案

## 3.1 目标

在不依赖 OCR 的前提下，尽可能把“公众号文章页”转成真实 `mp.weixin.qq.com` URL，再统一走 URL 入库和正文解析。

## 3.2 正式主路径

### 一级路径：直接 URL

- 若文章已在浏览器前台打开，直接读取地址栏 URL。

### 二级路径：微信文章页分享/复制链接

- 在微信文章页执行固定的 UI 自动化：
  - 点顶栏菜单
  - 尝试“复制链接”
  - 尝试“在默认浏览器打开”
  - 读取剪贴板或浏览器地址栏

### 三级路径：历史真链恢复

- 如果当前文章标题和正文前几百字与历史已入库文章相似，则用历史 URL 恢复。

### 四级路径：OCR 预检 + 真链恢复

- OCR 只用于：
  - 预检“当前页面是不是文章页”
  - 提取标题、作者、正文片段
  - 再尝试历史真链恢复

### 五级路径：OCR ingest fallback

- 只有前四层全部失败时，才把正文直接 OCR 入库。

## 3.3 需要继续强化的点

### A. 分享/复制链接热点标定

已有可配置项：

- `article_link_hotspots`
- `article_link_menu_offsets`

下一步继续做：

- 按微信窗口尺寸分 profile
- 按 Retina/非 Retina 分 profile
- 增加文章页顶栏存在性校验
- 增加复制成功后的剪贴板 URL 校验
- 增加浏览器接管后的 URL 域名校验

### B. 停止/暂停一致性

Focus 停止后必须满足：

- batch thread 停止
- loop 停止
- 前台状态卡立即刷新
- 不再继续微信 OCR

### C. 验证指标

建议把以下指标做成常驻面板：

- `direct_url_rate`
- `share_copy_url_rate`
- `history_resolve_rate`
- `ocr_preview_resolve_rate`
- `ocr_fallback_rate`
- `duplicate_rate`
- `stop_latency_sec`

目标：

- `URL-first 命中率 > 70%`
- `OCR fallback < 20%`
- `stop latency < 3s`

---

## 4. 当前研报质量问题拆解

## 4.1 当前主要问题

1. 同主题和异主题结果区分不够明显，主题漂移严重。
2. 实体结果不够具体，经常缺甲方、竞品、伙伴、预算、部门。
3. 证据不足时，输出会变空或变成低信息密度模板。
4. 不同 section 的主次不够分明，阅读像“信息堆积”。
5. 没有足够强的交叉验证和证据质量解释。

## 4.2 根因

1. 检索层：
   - query 扩展不够专业
   - 搜索意图没有分解成多个问题
   - 没有显式的“主题相关性校正”

2. 证据层：
   - 证据分层不足
   - 公司名、项目名、部门名未做稳健归一
   - 缺少相互印证和冲突检测

3. 推理层：
   - 没有把“甲方 / 竞品 / 伙伴 / 标杆案例 / 预算 / 招标节奏”分成不同专家模块
   - 没有 query-aware 的图谱记忆层

4. 输出层：
   - 没有足够强的结构模板和 section 证据配额
   - fallback 太弱

---

## 5. 同类方案调研结论

## 5.1 竞品产品可借鉴点

### AlphaSense

- 核心做法：
  - executive-summary-first
  - 每段结论都尽量和证据链接绑定
  - 把市场情报、公司情报、事件情报收敛到“可决策”的阅读流
- 借鉴点：
  - 每个核心判断都要带证据锚点
  - 需要证据密度和来源质量标签

### Perplexity

- 核心做法：
  - query -> deep research -> citations -> asset export
  - 进度与来源可感知
- 借鉴点：
  - 深度调研应显式显示进度和阶段
  - 研究结果不应只是一段 Markdown，要变成可复用资产

### Glean

- 核心做法：
  - collection/workspace 化组织知识
- 借鉴点：
  - 研报中心应该更像工作台而不是结果列表
  - saved views / tracked topics / compare workspace 很重要

### CB Insights

- 核心做法：
  - 公司/竞对/行业变化跟踪
  - decision-oriented intelligence
- 借鉴点：
  - compare matrix 不能停留在字段展示，要支持长期跟踪和差异高亮

## 5.2 开源/论文可借鉴点

### GraphRAG（Microsoft）

- 适合：
  - 把公司、部门、预算、案例、伙伴、政策、项目关系组织成图谱
  - 做 query-focused summarization
- 可借鉴：
  - 在研报中引入轻量知识图谱层，而不是只靠扁平检索

### STORM（Stanford）

- 适合：
  - 先做 research，再做 outline，再写 report
  - perspective-guided question asking
  - simulated conversation
- 可借鉴：
  - 先把问题拆成多个研究视角，再分别检索和归纳

### CRAG

- 适合：
  - 先评估 retrieval 质量
  - retrieval 差时自动切换到 web search 或 corrective 分支
- 可借鉴：
  - 加一个 retrieval evaluator，把“证据不足”变成“扩搜动作”，而不是直接空输出

### RAPTOR

- 适合：
  - 长文档、多来源、多层级摘要
- 可借鉴：
  - 用层级摘要减少长证据拼接时的信息噪声

---

## 6. 可行的研报升级方案

## 6.1 总体架构

建议升级为 6 层架构：

1. `Query Scope Router`
2. `Multi-source Retrieval`
3. `Evidence Normalization + Graph Memory`
4. `Expert Analyzers`
5. `Cross-validation + Scoring`
6. `Report Synthesis + Action Packaging`

### 第一层：Query Scope Router

把用户输入的主题拆成明确范围：

- 区域
- 行业
- 甲方类型
- 关键技术主题
- 商业目标

示例：

- `AI漫剧相关商机`
  - 行业：AIGC 动画 / AI短剧 / IP 内容工业化
  - 区域：未指定
  - 甲方：内容平台、IP 方、文旅/教育内容场景方
  - 商业目标：商机、合作、项目、预算、伙伴

### 第二层：Multi-source Retrieval

分 4 类源并发检索：

- 官方源
  - `gov.cn`
  - `ggzy.gov.cn`
  - 地方公共资源交易平台
- 官方/合规聚合源
  - `cecbid.org.cn`
  - 合规采购聚合
- 公开行业媒体与公开公众号页
- 已沉淀知识库/历史研报

### 第三层：Evidence Normalization + Graph Memory

核心不是“多搜几页”，而是把证据组织起来：

- 公司名归一
- 决策部门归一
- 预算金额归一
- 项目期次归一
- 领导/关键人物归一
- 联系入口归一

建议引入轻量知识图谱实体：

- `Company`
- `Department`
- `Project`
- `BudgetSignal`
- `Case`
- `Partner`
- `Competitor`
- `LeadershipSignal`
- `ContactChannel`

关系：

- `Company -> has_department -> Department`
- `Company -> announced_budget -> BudgetSignal`
- `Company -> awarded_project -> Project`
- `Company -> partnered_with -> Partner`
- `Competitor -> won_case -> Case`
- `Leader -> emphasized -> LeadershipSignal`

### 第四层：Expert Analyzers

把一份研报拆成 5 个专家模块并发分析：

- `甲方价值分析器`
  - 目标：给出高价值甲方 Top 3
  - 依据：预算、项目密度、战略方向、项目周期、公开采购行为

- `竞品威胁分析器`
  - 目标：给出高威胁竞品 Top 3
  - 依据：中标频次、标杆案例、产品/方案覆盖、区域强势度、生态绑定度

- `生态伙伴分析器`
  - 目标：给出高影响力伙伴 Top 3
  - 限制：优先牵线/集成/咨询/渠道型伙伴，降低纯产品厂商权重

- `招投标节奏分析器`
  - 目标：给出入场窗口、典型周期、投标前关键动作

- `领导与决策部门分析器`
  - 目标：识别高概率决策部门、近三年关注点、拜访顺序

### 第五层：Cross-validation + Scoring

每个实体必须至少给出：

- 名称
- 角色
- 定性价值等级
- 推理说明
- 证据链接
- 来源分层

证据打分维度：

- 主题相关性
- 来源可信度
- 新近性
- 多源一致性
- 角色匹配度
- 商机/预算/项目信号强度

### 第六层：Report Synthesis + Action Packaging

报告生成顺序建议固定为：

1. 执行摘要
2. 核心判断
3. 甲方 Top 3
4. 竞品 Top 3
5. 生态伙伴 Top 3
6. 预算与项目分布
7. 招投标节奏与入场窗口
8. 决策部门与领导关注点
9. 标杆案例
10. 短期/中期/长期行动卡
11. 风险与证据边界
12. References

---

## 7. 强 fallback 机制

即使没有命中具体公司，也不能空输出。

建议 fallback 分三级：

### Level 1：具体实体 fallback

如果找不到明确公司名：

- 输出“高价值角色化候选”
- 例如：
  - `省级数据局/政务服务管理局（待验证）`
  - `短剧内容平台运营方（待验证）`
  - `区域总包与咨询伙伴（待验证）`

### Level 2：高价值动作 fallback

必须给出高信息密度建议，例如：

- 应先搜哪些区域和哪类甲方
- 应优先追哪些采购/政策/平台信号
- 竞品常见短板和差异化切入点
- 从规划到招标的典型入场时机
- 年轻销售的拜访顺序建议

### Level 3：证据诊断 fallback

明确说明：

- 当前证据不足在哪里
- 已用哪些源
- 下一轮扩搜建议是什么

---

## 8. 映射到当前 Anti-FOMO 架构

当前可直接承接的模块：

- `backend/app/services/research_service.py`
  - 继续做 query router / retrieval evaluator / expert analyzers
- `backend/app/services/research_source_adapters.py`
  - 继续扩官方源和合规公开源
- `backend/app/services/research_job_store.py`
  - 承接深度调研长时任务和进度条
- `src/components/inbox/inbox-form.tsx`
  - 承接极速/深度模式、进度圆环、任务状态
- `src/components/research/research-center.tsx`
  - 承接 saved views / tracking topics / compare workspace
- `src/components/research/research-compare-matrix.tsx`
  - 承接甲方/竞品/伙伴正式 compare workspace
- `src/components/research/research-topic-workspace.tsx`
  - 承接字段级 diff、证据链接、版本工作台

---

## 9. 后续实现顺序

### 阶段 A：URL-first 采集器压实

1. 做微信文章页分享/复制链接热点标定 profile
2. 增加剪贴板 URL 校验和浏览器 URL 校验
3. 增加 URL-first 指标面板
4. 把 OCR 压到真正 fallback

### 阶段 B：检索与主题收敛升级

1. 新增 query decomposition
2. 新增 retrieval evaluator
3. 新增 topic relevance filter
4. 新增 7 年时间窗硬过滤

### 阶段 C：图谱与专家分析器

1. 公司/部门/预算/伙伴/案例轻量图谱
2. 甲方价值专家
3. 竞品威胁专家
4. 生态伙伴影响力专家
5. 招投标节奏专家

### 阶段 D：输出质量升级

1. section 证据配额
2. 版本级与字段级差异高亮
3. 强 fallback 动作建议
4. 评分贡献按来源类型聚合

---

## 10. 合规边界

本方案明确不包含：

- 付费墙绕过
- 登录墙绕过
- 未授权后台数据抓取
- CAPTCHA 绕过
- 个人微信订阅流 API 幻想式对接

可继续加强的方向只包括：

- 公开源
- 官方公开源
- 合规聚合源
- 用户自有或授权连接器
- 企业微信/企业采购合法接入

---

## 11. 参考资料

### 腾讯/微信官方

- WorkBuddy 接入微信指南  
  https://www.codebuddy.cn/docs/workbuddy/Wechat-Guide
- WorkBuddy 接入微信 ClawBot 指南  
  https://www.codebuddy.cn/docs/workbuddy/WeixinBot-Guide
- Remote Control  
  https://www.codebuddy.cn/docs/cli/remote-control
- 微信服务号文档：素材管理  
  https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/Getting_Permanent_Assets.html
- 企业微信开发者中心：获取会话内容  
  https://open.work.weixin.qq.com/api/doc/90000/90135/91774

### 竞品与产品参考

- AlphaSense Smart Summaries  
  https://www.alpha-sense.com/platform/smart-summaries/
- Glean Collections  
  https://docs.glean.com/user-guide/knowledge/collections/how-collections-work
- Perplexity Assets  
  https://www.perplexity.ai/help-center/en/articles/12528830-creating-assets-with-perplexity-overview
- CB Insights Platform  
  https://www.cbinsights.com/platform

### 开源与论文

- Microsoft GraphRAG  
  https://github.com/microsoft/graphrag
- STORM  
  https://github.com/stanford-oval/storm
- STORM Paper  
  https://arxiv.org/abs/2402.14207
- CRAG: Corrective Retrieval Augmented Generation  
  https://arxiv.org/abs/2401.15884
- RAPTOR  
  https://arxiv.org/abs/2401.18059
