# 《大模型应用开发 RAG实战课》对 Anti-FOMO 的升级启发与版本计划

更新时间：2026-04-21

参考资料：

- 本地 PDF：`/Volumes/One Touch 1/大模型应用开发 RAG实战课.pdf`
- 本次研读重点：文本分块、索引优化、检索前处理、检索后处理、响应生成、系统评估与系统优化

## 1. 先给结论

这本书对当前 `anti-fomo-demo` 最有价值的，不是再重复“RAG 是什么”，而是把研报系统拆成一条更完整的质量链路：

1. 检索前先做查询构建、查询改写、查询路由，而不是直接把用户输入拿去搜。
2. 检索层不能只靠“网页列表 + 规则打分”，要引入可维护的分块、索引、元数据过滤和混合检索。
3. 检索后不能直接交给大模型成稿，要补重排、压缩、校正和证据配额。
4. 生成不能只看文笔，要把“章节证据是否足够、结论是否可推进、哪些字段仍待补证”前台化。
5. 系统必须有评估闭环，否则每轮优化只能靠主观感受，无法稳定提升研报质量。

结论：这本书最值得直接纳入当前项目的，不是“再加一个向量库页面”，而是把现有的研究引擎从“搜索增强型成稿”升级为“可评估、可回填、可增量追问的 RAG 工作流”。

## 2. 当前系统已经做到的部分

对照书里的方法论，当前项目其实已经先走到了前半段：

- `backend/app/services/research_service.py`
  - 已有 scope planning、query plan、expanded plan、corrective retrieval。
  - 已有 RRF 风格的混合排序 `_hybrid_rank_hits`。
  - 已有 source rerank、官方源补证、证据密度、章节证据配额、report readiness。
  - 已有 follow-up 上下文注入、query plan 持久化、实体归一化、存量研报 rewrite/backfill。
- `backend/app/services/research_conversation_service.py`
  - 已有追问入口和会话持久化。
- `backend/app/services/knowledge_intelligence_service.py`
  - 已有 canonical org linking、coverage gaps、commercial summary、backfill 与断点续跑。
- `backend/app/services/work_task_service.py`
  - 已有研报导出、追问输入导出、交付补充信息透传。

也就是说，这个项目并不是从零开始补 RAG，而是已经实现了“查询规划 + 补证 + 护栏 + 交付”的业务骨架。

## 3. 当前与书中推荐体系之间的关键缺口

真正的差距集中在下面几层。

### 3.1 检索前处理还不够“结构化”

当前已有 query plan，但还缺 3 个更系统的能力：

- 元数据自查询
  - 目前的范围过滤主要靠 scope hints 和规则函数。
  - 还缺一层把用户问题自动翻译成 `区域 / 行业 / 官方源 / 时间窗 / 组织角色 / 证据类型` 过滤条件的机制。
- 检索路由
  - 现在主要还是“公开网页 + adapter + 存量报告重写”。
  - 还缺“当前问题应该优先走实时网页、历史研报、知识库、watchlist、commercial hub 哪条链路”的显式路由器。
- 追问模式的增量检索
  - 现在 `followup_context` 主要是把补充信息拼进 planning focus 和 prompt。
  - 还缺“基于上一版结论和新补证输入，只检索差异点并生成 delta evidence pack”的专门链路。

### 3.2 索引优化基本还没真正开始

书里最值得补课的是这一层，而当前系统这层最薄。

- 当前知识库主入口仍以 SQL / `ilike` / 元数据聚合为主，缺少真正的 chunk-level 检索索引。
- 研报生成目前也是对 source document 直接抽取和整合，缺少：
  - 递归分块
  - 标题/版式分块
  - 句窗检索
  - 父子块索引
  - 摘要到原文的分层索引
  - 文档级摘要索引
  - 元数据过滤型向量检索
- 当前还没有“研究语料索引层”这个明确的基础设施，因此 follow-up、知识复用、跨报告对照都还偏重规则和拼接，而不是复用检索资产。

### 3.3 检索后处理仍偏启发式

项目里已经有 heuristic rerank，但与书里的完整后处理相比，还缺：

- learned reranker
  - 例如 `Cross-Encoder` / `Jina` / `Cohere` 这一类更强的重排器。
- 上下文压缩
  - 目前 source excerpt 主要靠抽取和清洗，缺少“针对问题提取最相关句段”的压缩器。
- 时效加权
  - 目前有 recent filter，但缺少在最终排序阶段把“相关性 + 官方性 + 新鲜度”统一融合。
- correction pass
  - 现在有 corrective retrieval，但还缺“成稿前对关键章节再次校验，若证据不够则降级或回补”的后处理器。

### 3.4 响应生成还缺“按章节检索、按章节成稿、按章节自检”

当前已经有 section evidence quota，这是正确方向，但还没完全形成闭环：

- 仍以“先整份汇总，再成稿”为主。
- 缺“章节级 retrieval pack -> 章节级压缩 -> 章节级生成 -> 章节级 readiness”。
- 追问模式下缺“只重算受影响章节”的增量生成。
- 解决方案智囊后续要新增的可研报告、项目建议书，也需要建立在同一套章节级证据包之上，否则模板再专业也会被底层证据质量拖垮。

### 3.5 评估体系基本空白

这是目前最需要补的工程短板。

- 现在有 low-quality queue、guarded backlog、rewrite backfill，这些已经是很好的“弱监督资产”。
- 但还没有系统化指标，例如：
  - official hit recall@k
  - section evidence pass rate
  - bogus org rate
  - guarded backlog precision
  - follow-up delta evidence yield
  - knowledge retrieval hit quality
- 没有评估集和基线，后面继续调规则、换 reranker、改分块，都会缺少客观反馈。

## 4. 这本书最适合怎么改进当前三条主线

### 4.1 解决方案智囊

最值得吸收的是：

- 查询分解
  - 把用户目标拆成“场景、组织、预算、流程、伙伴、竞品、窗口”多个检索子目标。
- 路由检索
  - 政务/采购类先走官方和招采；客户洞察类先走公司官网/IR/团队页；方法论类再走行业媒体和历史研报。
- 追问式增量研究
  - 基于上一版研报和人工补充信息，只重检索新增线索和冲突线索。
- 模板化生成
  - 可研报告、项目建议书、exec brief 不直接用全文生成，而是用章节证据包驱动。

### 4.2 研报中心

最值得吸收的是：

- chunk-aware 检索
  - 对长网页、长公告、长 PDF 不是整篇拿来，而是按标题/段落/句窗切片。
- 分层检索
  - 先摘要召回，再拉正文；先父块命中，再补子块证据。
- 后处理重排
  - 把“官方源、主题相关、组织对齐、新鲜度、正文完整度”统一重排。
- 上下文压缩
  - 成稿只喂与章节目标最相关的证据句段，减少噪声和虚写。
- 章节级校验
  - 每个章节都要明确 `ready / degraded / needs_evidence`。

### 4.3 知识库

最值得吸收的是：

- 不再把知识卡主要当全文存储，而是当“可检索知识单元”的原料。
- 建立 chunk + parent document + metadata 的统一索引。
- 将 `report`, `knowledge entry`, `archive diff`, `watchlist digest`, `commercial hub` 统一纳入同一知识检索层。
- 对每个 chunk 补元数据：
  - `source_tier`
  - `domain`
  - `doc_type`
  - `published_at`
  - `region`
  - `industry`
  - `entity_names`
  - `watchlist/topic/account linkage`

## 5. 正式纳入后续版本的 P0-P2 计划

## P0：研究语料索引层与增量检索底座

目标：先把“可复用检索资产”做出来，解决当前 follow-up、知识库、长文召回的底层瓶颈。

范围：

- 新建统一的 research retrieval index 层，覆盖：
  - 抽取后的 source document
  - 知识库条目
  - 已存量研报
  - archive diff / compare export 文档
- 引入至少两种分块策略：
  - `标题/段落递归分块`
  - `句窗分块`
- 建立 parent-child 关系：
  - 子块负责召回
  - 父块负责给生成阶段补上下文
- 为 chunk 补齐 metadata：
  - 组织名、角色、区域、行业、来源级别、发布时间、文档类型、topic/watchlist/account 关联
- 建立混合检索：
  - `BM25 + dense retrieval`
- 为 follow-up 模式增加增量检索：
  - 新补证输入优先命中新 chunk
  - 上一版结论涉及的章节作为重检索目标
- 为知识页增加统一 retrieval service，而不是继续只走 `ilike`

优先改造模块：

- `backend/app/services/research_service.py`
- `backend/app/services/research_conversation_service.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/services/knowledge_intelligence_service.py`

验收：

- 同一问题在 follow-up 模式下，能引用到新增证据块，而不是只复述旧摘要。
- 知识库查询可以返回“证据片段 + 父文档 + 元数据”，不再只是全文模糊匹配。
- 长网页 / 长公告在研报中引用的证据粒度明显变细，低信号整段搬运下降。

## P1：检索后处理、章节级生成与可信度前台化

目标：把“能召回”升级为“能稳定写出有证据边界的研报”。

范围：

- 在 `_rerank_sources_hybrid` 之外增加可插拔 reranker：
  - 首选本地或 API 版 `Jina` / `Cross-Encoder`
  - 无外部模型时保留当前 heuristic 作为 fallback
- 增加 context compression：
  - 每个章节只保留最相关句段
  - 压掉长篇噪声、重复段和无效描述
- 增加时效加权和官方源加权的统一排序
- 将成稿改为章节级流水线：
  - section retrieval pack
  - section compression
  - section generation
  - section evidence check
- 对追问模式增加 delta output：
  - 哪些章节被新增证据改变
  - 哪些章节仍缺证
  - 哪些结论从 guarded 提升为 ready，或反向降级
- 将智囊输出的可研报告/项目建议书也挂到同一章节证据包上

优先改造模块：

- `backend/app/services/research_service.py`
- `backend/app/services/work_task_service.py`
- `src/components/research/*`
- `src/components/knowledge/*`

验收：

- 研报每个关键章节都能展示证据来源、证据密度、缺口与下一步补证动作。
- Follow-up 输出不再是泛化答复，而是“受影响章节 + 新证据 + 变化原因”。
- 解决方案智囊导出的可研报告和项目建议书，能够沿用同一套证据诊断和不足说明。

## P2：评估框架、缓存与系统优化

目标：让后续每轮质量优化都有可度量反馈，并把成本与延迟收下来。

范围：

- 基于现有资产建立 eval set：
  - low-quality review queue
  - guarded backlog
  - historical report versions
  - user follow-up conversations
  - compare/export evidence appendix
- 建立核心指标：
  - official hit recall@k
  - section evidence pass rate
  - bogus org rate
  - unsupported target account rate
  - follow-up delta evidence yield
  - rewrite improvement rate
- 建立 A/B 实验面板：
  - chunking strategy A/B
  - reranker A/B
  - query plan A/B
  - router policy A/B
- 增加 embedding cache 与 incremental re-index
- 为 backfill / rewrite / re-index 统一加入断点续跑和批量提交策略

优先改造模块：

- `backend/app/services/research_review_service.py`
- `backend/app/services/knowledge_intelligence_service.py`
- `scripts/research_regression_smoke.py`
- 新增 `scripts/rag_eval_*`

验收：

- 每次调整 query / chunk / rerank 策略后，都能跑出离线指标对比。
- 主库重建或回填索引时可分批、断点、低风险执行。
- 研报质量优化不再主要依赖人工抽查。

## 6. 推荐的实际推进顺序

不建议一上来就接外部大向量库或重做整套架构。更稳妥的顺序是：

1. 先做本地 research retrieval index 的最小版本
2. 再做 follow-up 增量检索和知识库统一检索入口
3. 然后接章节级 compression + rerank
4. 最后补 evaluation、缓存和 A/B

原因很直接：

- 没有检索资产，后处理和评估都无从谈起。
- 没有增量检索，追问模式再多 UI 也只是 prompt 拼接。
- 没有评估集，后续改 chunk/rerank 很容易出现“主观上好像更好，实际却退化”。

## 7. 明确不建议本轮优先做的事

- 不建议先上复杂 GraphRAG
  - 当前实体图谱主要用于组织归一化和展示，先把 chunk/index/retrieval 做稳更值当。
- 不建议先接重型外部向量数据库
  - 当前规模下，先做本地可控索引和评估比先上复杂基础设施更划算。
- 不建议把追问模式继续停留在“补充文本再发一次 prompt”
  - 这会把新增信息和旧证据混成一团，无法解释差异来源。

## 8. 已纳入总计划的方式

这份计划将作为对原有总计划的补充，纳入：

- `Phase 1` 研究质量升级
- `Phase 4` Knowledge Intelligence 与经营化输出
- 一条新的横向工程主线：`RAG 检索质量工程`

后续实际开发时，建议把它拆成：

- `Phase 1A` 检索前处理与索引层
- `Phase 1B` 检索后处理与章节生成
- `Phase 1C` 评估与系统优化

这样不会打乱原有项目路线，但能把影响研报质量的底层工程真正补齐。
