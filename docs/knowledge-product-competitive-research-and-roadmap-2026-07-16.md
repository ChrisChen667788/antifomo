# 知识库与决策文档产品竞品、开源调研及后续路线图（2026-07-16）

## 文档状态

- 调研日期：2026-07-16。
- 对应最新代码基线：`2.0.6+20260716`（本地工程实现，商业发布仍 blocked）。
- 本文最初是竞品结论和后续实施设计；截至 2026-07-16，`1.9.2` 至 `2.0.6-development` 的本地工程合同、API、迁移、测试和 `/studio` 已落地，但人类 qrels、真实专家样本、跨面 ACL 泄漏矩阵、生产 Skill 签名/benchmark、性能、安全、Office、视觉和客户验收尚未完成，因此不代表商业发布已批准。
- 当前 release promotion 仍被真实 `100+30` 专家校准、三行业盲测和客户验收阻断；后续开发不得用新功能覆盖这些既有门禁。
- 产品名按官方写法使用 `NotebookLM`；用户提到的 `notebookllm` 在本文统一指 NotebookLM。

## 调研方法与证据边界

本次只把以下资料当作能力事实：

1. 腾讯、Google、Notion 的官方产品页、帮助中心或腾讯官方开发者内容。
2. GitHub 仓库的 README、LICENSE 和项目官方文档。
3. Hugging Face、ModelScope 的模型卡和许可证字段。
4. SkillHub 页面与下载包的静态检查结果。SkillHub 包只下载到临时目录检查清单和文本，未安装、未执行。

对“竞品未提供某能力”的表述，严格解释为“本次检索的官方资料未见明确承诺”，不能推导为对方产品绝对不存在该能力。开源资产的许可证判断是工程准入建议，不替代正式法务审查。

## 一、结论摘要

### 1. 产品不应被重新定义为通用知识库

ima、NotebookLM 和 Notion 已经在“导入资料、围绕资料问答、生成通用内容”上建立了很低的使用门槛；WorkBuddy 又把结果文件、连接器、技能和任务执行串成了工作闭环。Anti-FOMO 若只补一个聊天式知识库，会在成熟产品的主场竞争。

更有防御性的定位应保持为：

> 微信/网页/文件信号 -> 可控证据集 -> 中国场景的研报、解决方案、可研、项目建议书 -> 可执行架构和验收证据

知识库是这条链路的证据底座，不是最终产品本身。

### 2. 当前已经形成的差异化

- 来源准入、主题范围、最低证据、问题覆盖、原子主张、引用完整度和实体真实性可以硬失败，而不是只给一个“看起来不错”的总分。
- 解决方案侧已经引入 QAW、ATAM、ADR、C4、PoA 和可执行验证，深度高于通用笔记产品的写作模板。
- 已有中国客户情报、甲方/竞品/伙伴、采购预算信号、正式 DOCX/PDF/PPTX 和 release-readiness 管理面。
- 微信收藏、网页、文件、RSS、Newsletter、浏览器扩展和专题追踪形成了连续采集入口。

### 3. 最明显的七项弱点

| 优先级 | 弱点 | 当前事实 | 直接后果 |
| --- | --- | --- | --- |
| P0 | 真语义检索不足 | `knowledge_retrieval_service.py` 的 dense 路径是字符 n-gram 哈希向量，不是经过语义训练的 embedding | 同义表达、长文跨段问题和中文行业术语召回不稳定 |
| P0 | 来源工作台不完整 | 有来源链接和证据账本，但没有 NotebookLM 式来源勾选、段落级跳转、修订版本和 artifact 失效提示 | 用户难以快速审查“这句话到底来自哪里” |
| P0 | 正式文档仍偏一次性生成 | `generation_execution.py` 先生成提纲，再用一次 `research_report.txt` 长调用合成主体，下游再治理 | 长报告易出现章节不一致，局部修改需要重跑大块内容 |
| P0 | 可研/项目建议书缺少版本化文档合同 | 有四类编译器和质量门，但尚未把国家/地方/行业大纲、必填字段、计算依据和缺口责任人做成版本化政策包 | 模板完整不等于审批口径完整，容易出现“有章节、无数据” |
| P1 | 团队知识治理偏弱 | 现有核心对象以 `user_id` 隔离，未见文档级 ACL、审批评论、知识 owner、验证状态和到期机制 | 不适合多人共创、企业权限继承和可信知识运营 |
| P1 | 连接器、技能、结果回流不成体系 | 有采集适配器和模型控制面，但没有受控技能注册表、权限声明、签名、沙箱及结果回写工作区 | 难以形成 WorkBuddy 式“研究 -> 执行 -> 交付 -> 沉淀”闭环 |
| P1 | Studio 输出形态单一 | 正式文档和 PPTX 较强，但没有由同一证据账本生成音频简报、思维导图、数据表、信息图等统一制品 | 知识消费和汇报场景覆盖弱于 NotebookLM |

### 4. 总体策略

- 借 NotebookLM 的“来源可见、可选择、可跳回、可生成多种制品”，不复制其学习工具定位。
- 借 Notion 的“权限感知搜索、结构化数据库、验证 owner、Agent 回写”，不扩张成通用协作文档平台。
- 借 WorkBuddy 的“任务结果面板、技能、连接器、记忆和 artifact 回流”，但保留 fail-closed 证据治理。
- 借 ima 的“微信低摩擦采集、共享/订阅知识库和段落引用”，继续强化中国内容入口。
- 把国家发改委现行可研大纲做成可版本化、可检查、可追溯的文档合同，而不是静态提示词。

## 二、当前产品能力基线

### 2.1 已具备能力

- 采集：URL、文本、RSS、Newsletter、文件、YouTube、浏览器扩展、小程序和微信收藏。
- 知识层：清洗、自动归档、收藏/专题、知识条目、持久化检索索引、专题版本和 Markdown 归档。
- 研究层：问题树、来源收集、官方来源偏置、来源准入、纠偏检索、claim-evidence ledger、反证、实体真实性过滤。
- 交付层：研报、解决方案、政府/企业可研、项目建议书、客户汇报 PPTX、DOCX、PDF。
- 架构层：QAW、ATAM、ADR、C4、NFR 追踪、PoA 和可执行验证。
- 治理层：模型策略控制面、diagnostics、低质量审计、独立复核、视觉/Office 门禁和 release-readiness。

### 2.2 代码级结构性限制

1. `backend/app/services/knowledge_retrieval_service.py` 的 `_dense_vector` 将检索词和 2/3-gram 哈希进固定维度，再以点积计算相似度。它提供了无需模型、可复现的本地基线，但不具备训练语义空间。
2. `backend/app/services/research/generation_execution.py` 的正式主体仍由单次 `research_report.txt` 调用完成。section retrieval context、问题树和证据摘要已进入提示词，但章节不是独立、可增量重建的编译单元。
3. `KnowledgeEntry` 主要保存正文、来源域、集合、置顶和 focus reference；`ResearchRetrievalIndexChunkRecord` 主要保存文本 chunk、来源 URL、层级和主题。尚无标准化 `source_revision`、页码/段落坐标、embedding 版本、ACL 或验证到期字段。
4. `ResearchTrackingTopic` 和 `ResearchReportVersion` 已为 Notebook/Studio 化提供了基础，但当前交互重心仍是专题、历史结果和交付卡，不是来源/问答/制品三栏工作台。

因此，下一阶段不是推翻现有证据链，而是在其上增加真正的文档解析、语义检索、来源定位、章节编译和团队治理。

## 三、竞品能力与策略对比

### 3.1 总体能力矩阵

| 维度 | 腾讯 ima | WorkBuddy | NotebookLM | Notion | Anti-FOMO 当前 |
| --- | --- | --- | --- | --- | --- |
| 知识组织 | 个人、共享、订阅知识库和知识库广场 | 可引用 ima 等知识源完成任务 | 每个 Notebook 是独立来源集合 | 页面、数据库、Teamspace 和连接器 | 知识条目、集合、专题、版本、归档 |
| 来源问答 | 支持引用知识库，公开资料展示数字引用回到原段落 | 任务中检索知识源并生成结果 | 仅选定来源问答，inline citation 可跳回原文位置 | Research Mode 给出来源，可限定工作区/连接器/网页 | 有来源链接和引用门，但交互式来源选择和原文定位弱 |
| Web 深度研究 | 公开资料侧重检索、总结和内容助手 | Deep Research 与任务执行结合 | Fast Research 和 Deep Research，可审查并导入报告/来源 | Research Mode 联合工作区、连接器和网页 | 有问题树、纠偏检索、准入账本和反证，来源 UX 较弱 |
| 任务执行 | 内容创作、知识问答、Agent/Skill 能力持续扩展 | 强：自主规划、文件操作、文档/表格/PPT/数据分析 | 主要生成 Notebook Studio 制品 | Agent 可创建/编辑页面、数据库并执行多步操作 | 强在研究和正式交付，跨应用执行和结果回流不足 |
| 协作与权限 | 共享知识库和内容生态 | 企业版接入腾讯文档、乐享和组织身份 | Notebook viewer/editor 分享 | 权限感知搜索、页面权限、评论、数据库、验证页面 | 以用户隔离为主，缺文档 ACL、评论审批、owner/expiry |
| 输出形态 | 写作、总结、播客/脑图等内容形态 | Word/Markdown/PDF/Excel/CSV/PPT/分析报告 | 报告、音视频概览、思维导图、数据表、幻灯片、信息图、测验 | 页面、数据库、研究结果及 Agent 生成内容 | 正式研报、方案、可研、建议书、DOCX/PDF/PPTX |
| 中国正式项目文档 | 本次官方资料未见专门审批合同 | 本次官方资料未见专门审批合同 | 本次官方资料未见专门审批合同 | 本次官方资料未见专门审批合同 | 已有专门编译器，但政策包、必填数据和计算血缘仍需深化 |
| 证据硬门禁 | 本次官方资料未见 release 级硬门说明 | 本次官方资料未见 release 级硬门说明 | 强 grounding/citation，未见正式交付硬失败体系 | 提供 citations 和 permissions，未见正式交付硬失败体系 | 主题、来源、主张、实体、质量、视觉和人审门禁较完整 |
| 架构权衡与验收 | 非公开主能力 | 通用 Agent 可做，但非专用合同 | 非主能力 | 非主能力 | QAW/ATAM/ADR/C4/PoA 是当前核心差异化 |
| Artifact 回流 | 内容可进入知识库 | 结果可上传腾讯文档、ima、乐享等 | 可导出 Docs/Sheets，导出后不同步 | Agent 直接写回页面和数据库 | 有归档和知识条目，缺统一 lineage、失效和审批回流 |

### 3.2 NotebookLM：最值得借鉴的是“来源审查体验”

官方帮助说明 NotebookLM 可导入 PDF、网站、YouTube、音频、Google Docs/Slides，并围绕来源回答；引用可以悬停查看原文并点击跳到来源位置。Studio 又把同一来源集合转成报告、音视频概览、思维导图、数据表、幻灯片和信息图。Deep Research 支持先浏览大量网站，再让用户审查报告和来源后导入 Notebook。

可借鉴：

- 左侧来源列表支持 include/exclude、标签、质量状态、版本和更新时间。
- 每个引用保存页码/段落/时间戳坐标，点击回到原始 passage。
- Deep Research 的“候选来源 -> 用户审查 -> 纳入受控证据集”流程。
- 所有 Studio 制品共用同一来源快照和 lineage，而不是各自自由生成。

不应照搬：

- Audio Overview、测验等不能早于证据链和正式文档合同；它们是知识消费形态，不是本产品的质量核心。
- Notebook 隔离不能破坏现有跨专题实体图和历史情报能力，应通过显式授权的跨 Notebook 检索解决。

官方依据：[NotebookLM 入门与来源](https://support.google.com/notebooklm/answer/16164461?hl=en)、[引用与来源定位](https://support.google.com/notebooklm/answer/16179559?hl=en)、[Studio 输出](https://support.google.com/notebooklm/answer/16206563?hl=en)、[Research 模式](https://support.google.com/notebooklm/answer/16215270?hl=en-5)。

### 3.3 Notion：最值得借鉴的是“团队知识治理”

Notion Research Mode 可以联合搜索页面、数据库、PDF、连接应用和 Web，并展示引用；Enterprise Search 强调权限感知连接器；Notion Agent 可以读取并编辑页面/数据库、处理多步任务；页面验证机制为知识页设置 owner 和可信状态。

可借鉴：

- 检索结果继承源文档 ACL，不能先检索后在展示层过滤。
- `owner + verified_at + expires_at` 作为正式知识状态，不用“收藏”代替可信。
- 研报结论、行动项和项目对象可写回结构化数据库，并保留来源 lineage。
- 评论、审批和版本差异进入正式文档发布流程。

不应照搬：

- 不建设完整块编辑器和通用数据库平台；优先实现与证据、项目和交付直接相关的有限对象。

官方依据：[Research Mode](https://www.notion.com/en-gb/help/research-mode)、[Enterprise Search](https://www.notion.com/product/enterprise-search)、[Notion Agent](https://www.notion.com/help/notion-agent)、[数据库](https://www.notion.com/help/intro-to-databases)、[页面验证](https://www.notion.com/help/guides/verify-knowledge-your-teammates-can-trust-with-page-verification)。

### 3.4 WorkBuddy：最值得借鉴的是“任务和结果闭环”

WorkBuddy 官方文档把自然语言任务、自主规划、文件/浏览器操作、深度研究、Word/Excel/PPT/分析报告结果面板串在一起；技能市场、Connector、个人记忆、模型路由和结果回传腾讯文档/ima/乐享组成了完整 Agent 工作面。

可借鉴：

- 每次任务显式展示计划、工具调用、文件变化、结果 artifact 和失败原因。
- Connector 统一权限声明和凭证范围；Skill 统一清单、启停、来源和风险提示。
- 研报生成后可以进入“建任务、补数据、生成表格、回写知识库”的连续流程。
- 模型自动路由应与任务策略、成本和证据门绑定，而不是只选择一个模型名。

不应照搬：

- 通用自主执行不能绕过来源准入、客户数据权限和正式交付审批。
- 第三方 Skill 默认禁用；不得直接执行来源不明的 shell、网络或文件权限。

官方依据：[产品概览](https://www.workbuddy.cn/docs/workbuddy/Overview)、[结果面板](https://www.workbuddy.cn/docs/workbuddy/Results)、[技能市场](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[Connector](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Connector)、[个人记忆](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Memory)、[模型](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Model)、[WorkBuddy 与 ima](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Knowledge-Base/IMA%20Knowledge%20Base/01-Workbuddy-IMA-Basic-Guide)。

### 3.5 腾讯 ima：最值得借鉴的是“微信入口和知识生态”

ima 已形成个人/共享/订阅知识库与广场形态，公开资料展示了 `@` 一个或多个知识库问答、数字引用跳回原文段落，以及 Agent、记忆和技能方向。它在中国用户的微信内容进入知识库方面天然占优。

可借鉴：

- 微信收藏导入后立即进入可检索来源，而不是停留在待处理收件箱。
- 共享/订阅知识库需要来源 owner、更新频率、质量标签和撤回机制。
- 公开知识包可作为 research source pack，但必须经过 Anti-FOMO 的来源准入和版本冻结。

不应照搬：

- 内容广场和公共知识库不能直接成为正式可研证据；发布者、原始来源和修订记录缺失时只能作为检索线索。

官方及腾讯来源：[ima 官网](https://ima.qq.com/)、[知识库引用与广场](https://cloud.tencent.com/developer/news/2546846)、[个人/共享/订阅知识库](https://cloud.tencent.com/developer/news/3792230)、[ima Agent 与记忆](https://cloud.tencent.com/developer/article/2663181)。

## 四、四类正式输出的真实差距

### 4.1 研报

当前优势是来源准入、问题树、反证、主张引用和实体真实性；弱点是正文仍偏长上下文一次合成，用户无法像 NotebookLM 一样逐来源审查和逐引用跳回。目标应从“生成一份报告”升级为“编译一组可重建、可审查的章节”。

### 4.2 解决方案

当前 QAW/ATAM/ADR/C4/PoA 已明显强于通用知识工具。主要问题不是框架缺失，而是业务主张、需求、架构决策、组件、测试和成本之间尚未全部落为同一有向图；方案局部变化后也缺少影响分析和差量重建。

### 4.3 可行性研究报告

国家发展改革委 `发改投资规〔2023〕304号` 明确政府投资项目原则上按 2023 版通用大纲编写，并强调必要性、方案可行性、风险可控性、多方案比选、全生命周期、投融资/财务、影响效果和风险管控。通用大纲包含 11 部分 39 条；企业项目另有参考大纲。项目建议书可参考通用大纲适当简化。

当前缺口：

- 尚未把“政府投资/企业投资/行业/地区/项目规模”转换成可执行的适用性规则。
- 章节存在不等于论证完成；每个字段需要 `evidence / calculated / assumption / missing / not_applicable` 状态。
- 投资估算、收益、敏感性分析和绩效指标需要公式、输入来源、版本和复核人，不应由模型直接写数字。
- 政策更新需要触发旧 artifact 失效和重审。

政策依据：[发改投资规〔2023〕304号](https://app.www.gov.cn/govdata/gov/202304/12/499093/article.html)、[政府投资项目通用大纲 PDF](https://www.gov.cn/zhengce/zhengceku/2023-04/11/5750844/files/5d4ac74386e84ead89684a6508368927.pdf)、[编写大纲说明 PDF](https://www.gov.cn/zhengce/zhengceku/2023-04/11/5750844/files/1f9fbc086883486f98433a945c32e50c.pdf)、[国家政务信息化项目建设管理办法](https://xxzx.mof.gov.cn/guizhangzhiduxxzx/202001/t20200122_3463129.htm)。

### 4.4 项目建议书

项目建议书不是缩短版营销方案。它需要先完成建设背景、必要性、目标、范围、主要建设内容、初步投资、资源条件、实施安排、效益和风险的立项级判断，并明确哪些结论将在可研阶段深化。系统应显式区分“立项假设”和“已验证事实”。

## 五、开源与社区资产准入清单

### 5.1 建议直接进入技术验证的候选

| 资产 | 许可证/来源 | 可用位置 | 结论 |
| --- | --- | --- | --- |
| [Docling](https://github.com/docling-project/docling) | MIT，官方仓库 | PDF/DOCX/PPTX/XLSX/HTML、版面、表格、公式、OCR、统一 JSON | `1.9.2` P0 解析器候选；通过 fixture 和性能基准后接入 parser adapter |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | MIT，LangChain 官方仓库 | LangGraph 研究编排、模型分工、MCP/search 接口、评测方式 | 复用编排模式和可拆模块；不得直接替换现有 evidence gate |
| [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) / [Qwen3-Reranker-8B](https://huggingface.co/Qwen/Qwen3-Reranker-8B) | Apache-2.0 模型卡 | 中文/多语 embedding 与 reranking | 进入 shadow A/B；是否采用由本项目三行业 qrels 决定，不按公开榜单直接升级 |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) / [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | MIT / Apache-2.0 模型卡 | dense+sparse+multi-vector 与轻量 rerank | 作为成本、延迟较低的基线；同样必须跑中文 hard-negative 基准 |

ModelScope 可用于国内下载和离线镜像验证：[BGE-M3](https://modelscope.cn/models/BAAI/bge-m3)、[Qwen3 Embedding GGUF](https://modelscope.cn/models/Qwen/Qwen3-Embedding-8B-GGUF)。生产制品必须记录上游 commit/model revision、哈希、许可证快照和回滚版本。

### 5.2 只借鉴架构，不整体接入

| 资产 | 借鉴点 | 不整体接入原因 |
| --- | --- | --- |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 深文档解析、可追踪引用、知识库与 Agent 交互 | 产品架构和运行栈较重，整体替换会破坏现有 evidence/release 体系；先做 adapter 和 UX 对照实验 |
| [STORM](https://github.com/stanford-oval/storm) | 多视角提问、检索、提纲、带引用长文写作 | 适合研究写作流程参考；需先完成依赖和许可证清单，且不能替代中国正式文档合同 |
| [GraphRAG](https://github.com/microsoft/graphrag) | 实体/关系抽取、社区摘要、全局问题 | 索引成本高；只用于跨专题实体洞察和全局关系问题，不作为默认检索路径 |
| [PIKE-RAG](https://www.microsoft.com/en-us/research/articles/pike-rag-enabling-industrial-llm-applications-with-domain-specific-data/) | 知识原子化、任务分解和异构知识组织 | 先独立实现适配当前 claim-evidence ledger 的模式，不把研究原型直接放进生产 |
| [NVIDIA Skills](https://github.com/NVIDIA/skills) | verified skill、签名、skill card、eval dataset、benchmark | 借治理规范，运行时仍需按 Anti-FOMO 的权限、网络和证据边界实现 |

### 5.3 暂缓或拒绝默认复用

| 资产 | 原因 | 处理方式 |
| --- | --- | --- |
| [MinerU](https://github.com/opendatalab/MinerU) | 仓库许可证含附加条件；ModelScope 的 [MinerU2.5-2509-1.2B](https://modelscope.cn/models/opendatalab/MinerU2.5-2509-1.2B) 标注 AGPL-3.0 | 可隔离评测，不进入默认商业发行包，法务批准后再决定服务化边界 |
| [Jina Embeddings v3](https://huggingface.co/jinaai/jina-embeddings-v3) | 模型卡为 CC-BY-NC-4.0，不适合作为未另行授权的商业默认 | 不进入默认候选池 |
| 来源、许可证或作者不可核验的 SkillHub 包 | 供应链、授权和指令注入风险 | 只摘取公开流程思想，重新按官方标准独立实现，不复制包内内容 |

### 5.4 SkillHub 静态审查结果

SkillHub 自述提供技能目录、TRACE 和安全扫描，但目录存在作者、许可证和版本元数据不完整的社区包。以下仅作为需求样例：

- [gz-feasibility-report](https://skillhub.cn/skills/gz-feasibility-report)：11 章、表单化资料收集、分章/合规模式很贴近可研工作流；但包内外版本号不一致，且不能用社区模板替代发改委和地方正式文件。
- [long-report-agent](https://skillhub.cn/skills/long-report-agent)：章节规划、有限并行、跨章一致性和增量更新值得借鉴；包内许可证证据不完整，暂不复制代码。
- [sa-pro-workbench](https://skillhub.cn/skills/sa-pro-workbench)：C4、TOGAF、ArchiMate、ADR、RFP/SOW artifact 清单可用于检查覆盖面；不作为权威标准来源。
- [it-consulting-workbench](https://skillhub.cn/skills/it-consulting-workbench)：咨询生命周期、TCO/ROI/FinOps 流程可参考，但包声明禁止商业使用，不复用内容。
- [search-orchestrator](https://skillhub.cn/skills/search-orchestrator)：查询锚定、并行多源搜索、收敛和审计是好模式；只独立实现思路。

后续 Skill Runtime 必须要求：`manifest + immutable version + publisher provenance + license + signature + permission declaration + network/file scope + prompt-injection scan + eval dataset + benchmark + quarantine`。任何一项缺失都不得默认启用。

## 六、后续版本实施方案

### 6.1 `1.9.2`：True Retrieval and Source-Grounded Notebook

目标：把现有专题和知识条目升级为可审查来源、真语义检索和段落引用的研究 Notebook，同时保持 fail-closed。

后端与数据：

- 新增 `ResearchNotebook`、`NotebookSource`、`SourceRevision`、`SourcePassage`、`NotebookArtifact`、`ArtifactSourceBinding`。
- `SourcePassage` 保存页码、段落、表格单元格、视频/音频时间戳和 parser 坐标；引用禁止只存 URL。
- 建立 parser adapter，首选用 Docling 做影子解析；现有清洗器保留为 fallback，并记录 parser/version/hash。
- 建立 embedding/reranker provider contract，在 Qwen3 与 BGE 上 shadow A/B；索引同时记录 embedding model、dimension 和 revision。
- 保留现有 hash-dense 作为离线确定性 baseline，不再标记为生产语义检索。
- 现有 `KnowledgeEntry`、专题版本和 Markdown archive 可迁移为 Notebook source/artifact，但原记录不删除。

API 与前端：

- `/api/research/notebooks`：创建、列表、归档、复制。
- `/api/research/notebooks/{id}/sources`：导入、启停、标签、版本、重解析、准入状态。
- `/api/research/notebooks/{id}/chat`：显式 `included_source_ids`，回答返回 passage citation。
- `/api/research/passages/{id}`：返回原文定位和可视上下文。
- `/api/research/notebooks/{id}/artifacts`：列出制品 lineage、来源快照和 stale 状态。
- UI 采用 Sources / Chat / Studio 三栏；移动端按标签切换，不能压缩成三列。

测试与 release gate：

- 三行业各 100 条人工 qrels，合计至少 300 条 query，包含同义词、跨段、数字、表格和跨行业 hard negatives。
- 相比现有 hash baseline，`nDCG@10` 提升至少 15%，并达到 `>=0.78`；`Recall@20 >=0.90`；关键跨行业误召回 `<=2%`。
- 100 份多格式文档解析集，正文顺序/表格/页码定位通过率 `>=98%`；解析失败必须显式降级。
- citation click-back 命中正确 passage `>=98%`；未选来源泄漏为 `0`；无法定位的主张不得显示为已引用。
- artifact 所依赖 source revision 变化后 60 秒内标记 stale。

非目标：本版不建设多人协作，不添加音频/信息图，不整体迁移到 RAGFlow。

### 6.2 `1.9.3`：China Decision Document Contract Packs

目标：把研报、解决方案、政府/企业可研和项目建议书从提示词模板升级为版本化、可计算、可审计的文档合同。

后端与数据：

- 新增 `DocumentPackDefinition`、`PolicyPack`、`RequirementField`、`EvidenceCell`、`AssumptionRegister`、`CalculationSheet`、`ReviewDecision`。
- 首批一方维护包：`research_report_cn_v1`、`solution_proposal_cn_v1`、`government_fsr_2023_v1`、`enterprise_fsr_2023_v1`、`project_proposal_cn_v1`。
- 每个字段必须处于 `evidence / calculated / assumption / missing / not_applicable` 之一，并保存 owner、依据和复核状态。
- 政策包保存发文机关、文号、发布日期、施行日期、适用范围、原文哈希和 supersedes 关系。
- 投资估算、财务分析、敏感性和绩效指标通过确定性公式服务生成，模型只能解释，不能创造输入数字。
- 政府投资和企业投资采用不同适用性规则；行业/地方扩展包只能叠加，不能静默覆盖国家基线。

前端：

- 新建“资料缺口与责任人”视图，生成前先回答缺失信息，而不是让模型补齐。
- 章节树展示适用条款、证据、公式、假设、审阅人和阻断原因。
- 输出附政策/数据版本清单、假设登记册、计算说明和未决项，不把内部诊断词带入客户正文。

测试与 release gate：

- 2023 版政府可研通用大纲适用项覆盖率 `100%`；所有必填字段都有状态、owner 和证据/缺口说明。
- 金额、比例、日期和绩效指标的无来源生成数为 `0`；公式重算结果与导出文档一致率 `100%`。
- 政策包更新会使受影响 artifact 进入 stale/review，不影响的 artifact 不误报。
- 政府可研、企业可研、项目建议书三类至少各 20 份脱敏真实样本由专家盲审；模板 fixture 不代替人工结果。

非目标：本版不承诺自动完成全部工程咨询工作，缺数据时只交付缺口清单或证据受限草稿。

### 6.3 `1.9.4`：Claim Graph and Incremental Section Compiler

目标：消除长报告一次性合成，建立从问题、证据、主张到章节和 artifact 的可增量编译图。

后端与数据：

- 新增 `ResearchQuestionNode`、`ClaimNode`、`SectionPlan`、`SectionDraft`、`ConsistencyFinding`、`ArtifactBuild`。
- 每个 section 只接收其允许的问题、accepted claims 和 passage citations；禁止读取未准入原始 chunk。
- 最多 4 个有界章节 worker 并行，最后由 consistency challenger 检查实体、术语、金额、时间、方案选项和结论冲突。
- 构建 dependency DAG；来源、政策或数据变化只重跑受影响章节，并生成前后 diff。
- 章节被拒绝时保留其失败证据，不能由总报告合并阶段偷偷补写。

前端：

- 章节状态显示 waiting / drafting / challenged / blocked / approved / stale。
- 支持只重建选中章节、查看 evidence diff、接受/驳回 consistency finding。
- 报告正文每个结论可展开到 claim -> evidence -> source revision。

测试与 release gate：

- 黄金样本中关键实体、数字、术语和推荐方案的跨章冲突为 `0`。
- critical claim 的 passage citation coverage `100%`，普通 claim `>=95%`。
- 单一来源修订时，`>=90%` 未受影响章节不得重跑；差量结果通过整报一致性检查。
- 远程模型或章节 worker 失败时，只阻断受影响章节，禁止把 fallback 草稿提升为客户成品。

### 6.4 `1.9.5`：Collaborative Knowledge OS

目标：增加完成企业知识运营所必需的权限、可信状态、评审和有限连接器，不扩张成通用 Notion 克隆。

后端与数据：

- 新增 `KnowledgeSpace`、`SpaceMembership`、`DocumentAcl`、`VerificationRecord`、`ReviewThread`、`ConnectorBinding`、`SyncCursor`。
- ACL 在召回前生效，索引和缓存保存 security label；禁止“先全库召回、后展示过滤”。
- 知识对象支持 owner、verified_at、expires_at、superseded_by 和撤回原因。
- 首批连接面：现有微信/Web/上传入口、受控本地目录、只读 MCP connector contract；腾讯文档、飞书、Notion adapter 进入单独凭证与权限评审后再开 feature flag。
- 研报、行动项、风险和项目对象可以回写 Space，但保留 artifact/source lineage 和审批记录。

前端：

- Space 成员、角色、文档权限、评论、审批、验证到期和变更通知。
- 搜索结果显示权限来源、owner、可信状态和更新时间。
- 发布前展示“哪些用户将获得哪些来源/结论”的权限预览。

测试与 release gate：

- 多租户、跨角色、撤权、缓存、导出和引用 click-back 的权限泄漏为 `0`。
- 撤权后搜索、已有 chat、artifact 下载和 deep link 在 SLA 内同步失效。
- 过期或撤回知识不能支撑新的 critical claim；历史 artifact 保留审计但标记状态。
- 连接器凭证不进入日志、prompt 或导出 artifact。

### 6.5 `1.9.6`：Governed Agent and Skill Runtime

目标：把研究、补资料、计算、架构验证和交付动作包装成可复用、可审计技能，同时控制供应链与权限风险。

运行时：

- Skill manifest 必含 publisher、immutable version、hash、license、signature、input/output schema、模型策略、文件/网络/连接器权限、预算和超时。
- 安装经历 quarantine -> static scan -> policy review -> dry run -> benchmark -> approved；第三方技能默认关闭。
- 执行环境默认无 shell、最小文件目录、域名 allowlist 和短期凭证；高风险动作要求人确认。
- 每次运行记录 plan、tool calls、输入来源快照、输出 artifact、成本、失败原因和回滚信息。
- 支持 MCP connector，但 MCP 返回内容仍按不可信输入处理，不能绕过 evidence admission。

首批一方 Skill：

1. `deep-research-orchestrator`：问题分解、并行检索、收敛、反证和证据审计。
2. `government-fsr-intake`：政府可研资料问卷、条款适配和缺口清单。
3. `project-proposal-compiler`：立项级假设、范围、投资和风险编译。
4. `solution-architecture-workbench`：QAW/ATAM/ADR/C4/PoA 编排。
5. `evidence-and-entity-auditor`：主张引用、实体真实性和跨章一致性复核。

测试与 release gate：

- 未签名、许可证缺失、权限超范围或 benchmark 不达标的 Skill 无法进入 approved。
- prompt injection fixture 不得触发未声明网络、文件或连接器操作。
- dry run 与正式运行的计划差异可解释；文件/数据库变化可预览和审计。
- Skill 失败不能改变 artifact 的 approved 状态，也不能将低质量结果写回可信知识区。

### 6.6 `2.0.0`：Multimodal Decision Studio and Commercial Readiness

目标：在同一 claim-evidence ledger 上生成多形态决策制品，并完成企业发布所需的性能、成本、安全和客户验收。

Studio 输出：

- Executive audio brief：含 transcript、章节、引用和无障碍文本。
- Mind map：节点绑定 question/claim/section，可跳回证据。
- Data table：结构化提取、单位和公式明确，可导出 XLSX/CSV。
- Slide deck / infographic：只消费 approved claims，图表数据来自 calculation sheet。
- 正式 DOCX/PDF/PPTX 继续作为主要交付，不被多媒体输出替代。

一致性与 readiness：

- 所有制品保存同一 source snapshot、policy pack、claim graph 和 model/skill revisions。
- 跨制品 critical claim 一致率 `100%`，普通 claim `>=98%`；任何冲突阻断整套发布。
- 音频/图形不能省略正文中的关键限制、假设和风险。
- 建立端到端成本、P95 延迟、并发、数据保留、备份恢复和审计导出门禁。
- 完成医疗、金融、文旅三行业真实 100+30 专家校准、客户验收和独立视觉/Office 复核后，才允许商业 release-ready。

## 七、跨版本指标与治理

| 指标域 | 核心指标 | 进入 release-readiness 的条件 |
| --- | --- | --- |
| 检索 | nDCG@10、Recall@20、hard-negative false positive、官方来源 recall | 真实人工 qrels，不接受仅合成 fixture |
| Grounding | critical claim coverage、passage click-back accuracy、source leakage | critical 100%，定位 >=98%，泄漏 0 |
| 正式文档 | 大纲适用项覆盖、必填状态、无来源数字、公式重算 | 覆盖/重算 100%，无来源数字 0 |
| 一致性 | 跨章实体/数字/术语/推荐冲突、跨制品一致性 | critical 冲突 0 |
| 安全 | ACL 泄漏、Skill 越权、连接器凭证暴露 | 全部 0 |
| 人工质量 | 专家 undeliverable recall、行业偏差、客户 acceptance | 沿用现有 `1.8.4-1.9.1` 人工门禁，不能由自动分数替代 |
| Artifact | Office roundtrip、视觉 baseline、占位符、可编辑性 | 现有门禁继续生效并增加 lineage/stale 检查 |

## 八、明确不做的捷径

- 不以“一键更新到最强模型”替代检索、文档合同和人审。
- 不把 RAGFlow、GraphRAG 或某个 Agent 框架整体迁入后宣称升级完成。
- 不执行来源不明的 SkillHub 包，不复制带非商用限制的技能内容。
- 不让模型补齐预算、收益、客户名称、政策条款或项目事实。
- 不先生成音频/PPT，再事后尝试给内容找引用。
- 不把 deterministic fixture、静态模板覆盖或本地绿色测试冒充真实专家/客户验收。

## 九、建议实施顺序

1. 先完成 `1.9.2` 的真语义检索、parser、passage citation 和 Notebook 来源面；这是所有后续能力的证据基础。
2. 再完成 `1.9.3` 文档合同和政策包；没有字段状态与计算血缘，不应扩大自动生成范围。
3. 以 `1.9.4` 把现有长调用拆成 claim/section 编译图，解决长文质量和局部重建。
4. `1.9.5` 扩展团队治理，`1.9.6` 才开放受控 Agent/Skill 生态。
5. `2.0.0` 最后增加多模态 Studio，并与既有人审、客户、视觉、Office、安全和性能门一起收口。

这一顺序保持了当前产品的差异化：先提高“证据与正式决策文档”的可靠性，再提高协作、自动化和输出丰富度。

## 十、2.0.1-2.0.6 工程落地更新（2026-07-16）

本调研前半部分的“当前弱项”描述的是实施前代码基线。随后本地工程已继续推进到 `2.0.6-development`：

- `2.0.1` 已增加现有知识/研报的真实 Notebook 激活，以及从原始 qrel/解析 case 计算指标的服务端基准。
- `2.0.2-2.0.3` 已把正式文档、Claim 编译、100 条独立复核和实体真实性阈值注册为不可绕过的 validation suite。
- `2.0.4-2.0.5` 已把跨面权限、Skill 安全、多形态一致性、Office roundtrip 和日夜视觉确认纳入同一证据合同。
- `2.0.6` 已增加性能/成本、队列恢复、备份恢复、审计导出和外置模型盘 fail-closed 的验收合同与本机非破坏性探针。
- 新增不可变运行记录、审阅者分离、raw artifact URI、输入摘要和 SHA-256 审计链，并在 `/studio` 展示六个版本的实现/验收双状态。

上述更新解决了“没有统一落地和量化入口”的工程弱项，但没有生成真实人工证据。300 条 human qrels、正式文档专家样本、100/100 独立复核、500 条实体标注、生产安全矩阵、Office/视觉确认、生产式压测/恢复演练和客户验收仍为 `blocked`。完整合同见 `docs/decision-studio-release-program-v2.0.1-v2.0.6.md`。
