# Anti-FOMO Competitive Landscape and Post-2.0.6 Roadmap

Research snapshot: `2026-07-17`

Product baseline: `2.2.0+20260718`

Roadmap status: engineering contracts implemented on an explicitly authorized non-release branch; commercial release status remains `blocked`.

## 中文执行摘要

本轮调研覆盖国内的腾讯 ima、WorkBuddy、飞书知识问答、Kimi 深度研究、WPS AI、百度文库，以及国外的 NotebookLM/Gemini Notebook、Notion AI、ChatGPT、Claude、Microsoft 365 Copilot、Perplexity、Glean，并复核了 Docling、MinerU、Open Deep Research、RAGFlow、GraphRAG、PaperQA2 和 Qwen3 Embedding/Reranker 等开源或模型资产。

核心判断：

1. “深度研究 + 引用 + 长报告”已经成为通用能力，不能继续作为唯一卖点。
2. 企业知识库的主要壁垒已转向现成内容图谱、身份权限、连接器和协作，Anti-FOMO 不应复制飞书、Notion 或 Microsoft 365。
3. PPT、Word、Excel、图表和多形态输出也在快速普及，真正差异不再是“能导出”，而是每个输出块能否追溯证据、公式、政策、假设和审核状态。
4. Anti-FOMO 最有价值的定位是“证据绑定的中国决策文档与验收工作台”：从微信/网页/文件信号出发，冻结证据集，形成 Claim Graph，编译研报、解决方案、可研和项目建议书，再绑定 QAW/ATAM/ADR/C4 与可执行验收证据。
5. 当前最大短板不是少一个功能，而是 `2.0.1-2.0.6` 已有验收计算器仍缺真实人工、专家、客户、Office、视觉、安全、压测和恢复证据。商业发布状态必须继续保持 `blocked`。

优化后的版本顺序：

| 版本 | 中文目标 | 状态 |
| --- | --- | --- |
| `2.0.7` | 发布证据收口，冻结功能扩张并完成全部真实门禁 | engineering implemented；acceptance blocked |
| `2.1.0` | 可编辑研究任务书、问题树、候选来源审核、实时控制与运行对比 | engineering implemented；acceptance blocked |
| `2.1.1` | 人工 qrel 驱动的混合检索、重排和多解析器质量工程 | engineering implemented；real benchmark blocked |
| `2.1.2` | 保留证据血缘与人工修改的正式文档结构化编辑器 | engineering implemented；Office/visual blocked |
| `2.1.3` | 企业身份、ACL 和飞书/腾讯文档/Notion/Microsoft 365 受控连接器 | engineering implemented；production matrix blocked |
| `2.1.4` | 可恢复、可审批、可回放、可回滚的受控 Agent 运行体系 | engineering implemented；security benchmark blocked |
| `2.1.5` | 医疗、金融、文旅三行业正式证据包和专家标尺 | engineering implemented；expert artifacts blocked |
| `2.2.0` | 多人决策工作台、企业部署能力和三行业真实客户试点收口 | engineering implemented；customer signoff blocked |

执行原则：版本按证据门禁推进，不按日历自动升级；任何模型升级、来源数量、报告长度或视觉效果都不能覆盖证据、权限、正式文档合同和客户验收的硬失败。

## 1. Research method and evidence boundary

This review updates the earlier `2026-07-16` comparison after the local `2.0.1-2.0.6` engineering line was completed. It answers a different question: given what competitors publicly ship now and what Anti-FOMO has actually implemented, what should be built next?

Evidence rules:

- Product capabilities are taken primarily from official product pages, help centers, release notes, and first-party repositories available on `2026-07-17`.
- `Strong / Medium / Weak / No public evidence` in the matrix describes breadth visible in official material, not an independently measured quality score.
- Public marketing claims are recorded as vendor claims. This review did not purchase every enterprise plan or run a controlled hands-on benchmark against every product.
- Anti-FOMO capability statements distinguish local engineering implementation from release-approved evidence. A local API, calculator, or fixture does not equal expert, customer, security, Office, or visual acceptance.
- No market-share or revenue conclusion is made without a primary source. The output is a product and execution comparison, not a market-sizing report.

## 2. Executive conclusion

### 2.1 The market has moved

Three formerly differentiating capabilities are becoming baseline features:

1. **Deep research with citations is commoditizing.** Kimi, ChatGPT, Claude, Perplexity, Notion Research, Microsoft 365 Copilot Researcher, and NotebookLM/Gemini Notebook all publicly describe multi-step research with source links or citations.
2. **Internal knowledge plus web search is becoming a suite feature.** Feishu, Notion, Microsoft 365, Perplexity, Glean, ChatGPT Apps, and Claude Integrations combine internal context with web or connected services. Permission-aware retrieval and connectors are no longer optional for enterprise products.
3. **Multiform artifact generation is converging.** Kimi, WPS, Microsoft 365, WorkBuddy, Perplexity, and Gemini Notebook can produce or edit reports, slides, spreadsheets, charts, or downloadable files. Generating a PPTX or long report alone is not a durable moat.

### 2.2 The defensible position

Anti-FOMO should not become another generic knowledge base, office copilot, or unrestricted deep-research chat. Its defensible chain is:

`WeChat/web/file signals -> reviewable source snapshot -> claim/evidence graph -> Chinese formal decision documents -> architecture tradeoffs -> executable acceptance evidence`

The product should compete on **decision assurance**, specifically:

- a frozen, repeatable evidence set instead of a non-reproducible one-time search;
- source revision, passage coordinates, claim state, counter-evidence, and stale propagation;
- Chinese research report, solution, feasibility study, and project-proposal contracts;
- formula, assumption, policy, entity, and cross-chapter lineage;
- QAW/ATAM/ADR/C4 and proof-of-architecture tied to acceptance evidence;
- fail-closed release rules that do not promote polished but unsupported output.

### 2.3 The immediate decision

Do not start a broad connector, agent, or artifact expansion while release readiness is still blocked. The next version must be `2.0.7 Release Evidence Closure`. It freezes feature expansion and completes the real evidence required by the already implemented `2.0.1-2.0.6` contracts. Only then should the roadmap move to research control, retrieval quality, document editing, enterprise connections, and agent operations.

## 3. Competitive landscape

### 3.1 Product archetypes

| Archetype | Representative products | Their strongest default advantage | Implication for Anti-FOMO |
| --- | --- | --- | --- |
| Personal knowledge notebook | Tencent ima, NotebookLM/Gemini Notebook | Low-friction source collection, source-scoped Q&A, learning artifacts | Match source control and click-back; do not clone a general note editor |
| Enterprise knowledge and collaboration | Feishu, Notion, Glean, Microsoft 365 Copilot | Existing content graph, identity, permissions, collaboration, connectors | Integrate selectively; do not try to replace their whole workspace |
| Deep-research assistant | Kimi, ChatGPT, Claude, Perplexity, Notion Research | Broad web research, visible progress, citations, multi-turn refinement | Differentiate on repeatability, formal contracts, hard gates, and acceptance |
| Office artifact suite | WPS AI, Microsoft 365 Copilot, Kimi PPT, Baidu Wenku | Native editing, templates, Office roundtrip, visual polish | Build an evidence-aware structured editor and robust Office export, not a generic AIPPT |
| Executing work agent | WorkBuddy, Claude Integrations, ChatGPT Apps, Glean Agents | Planning, tools, connected actions, file operations | Keep skills governed, checkpointed, budgeted, and bound to evidence admission |

### 3.2 Capability matrix

Legend: `Strong` means broad first-party coverage is visible; `Medium` means partial or plan-dependent coverage; `Weak` means secondary to the product; `No public evidence` means this review found no first-party proof, not that the capability is impossible.

| Product | Source-grounded research | Enterprise knowledge / ACL | Editable artifacts | Agent execution | Chinese formal-document contracts | Public hard evidence gates |
| --- | --- | --- | --- | --- | --- | --- |
| Tencent ima | Medium | Weak/Medium | Weak | Weak | No public evidence | No public evidence |
| Tencent WorkBuddy | Medium | Medium through Tencent Docs/ima | Strong | Strong | Weak | No public evidence |
| Feishu Knowledge Q&A | Medium | Strong | Strong in Feishu workspace | Medium | Weak | No public evidence |
| Kimi Deep Research | Strong | Weak/Medium | Strong | Medium | Weak | Weak |
| WPS AI | Medium | Medium | Strong | Medium | Weak/Medium via templates | No public evidence |
| Baidu Wenku AI | Medium | Weak | Strong for documents/PPT | Medium | Weak/Medium via templates | No public evidence |
| NotebookLM / Gemini Notebook | Strong | Medium in Google context | Strong and expanding | Medium/Strong, experimental | No public evidence | Weak |
| Notion AI | Strong | Strong | Strong | Strong | No public evidence | Weak |
| ChatGPT | Strong | Strong with Apps/sync | Strong | Strong | No public evidence | Weak |
| Claude | Strong | Strong with integrations | Strong | Strong through MCP/integrations | No public evidence | Weak |
| Microsoft 365 Copilot | Strong | Strong | Strong | Strong | No public evidence | Weak |
| Perplexity | Strong | Medium/Strong | Strong | Strong | No public evidence | Weak |
| Glean | Medium/Strong | Strong | Medium | Strong | No public evidence | Weak |
| Anti-FOMO `2.2.0-development` | Medium; hybrid contract implemented, real benchmark pending | Medium; identity/ACL sync contract implemented, real connector matrix pending | Medium; evidence-aware editor implemented, Office/visual approval pending | Medium; durable Agent contract implemented, production signing pending | Strong engineering contract | Strong engineering contract; real evidence still blocked |

The matrix exposes the central risk: Anti-FOMO's distinctive columns are the last two, but they are not commercially credible until the outstanding human and operational evidence is completed.

## 4. Product findings

### 4.1 Domestic products

#### Tencent ima

The official surface exposes conversations, knowledge bases, discovery, and history. Its competitive value is low-friction personal knowledge use in the Tencent ecosystem, not public proof of formal-document governance. Anti-FOMO should preserve its WeChat-heavy intake advantage and make source state more explicit than a generic knowledge library.

Source: [Tencent ima](https://ima.qq.com/).

#### Tencent WorkBuddy

WorkBuddy publicly positions itself as an all-scenario AI office workbench with natural-language task creation, autonomous planning, local-file operations, documents, spreadsheets, PPT, data analysis, deep research, skills, connectors, memory, models, and result previews. This overlaps heavily with generic task execution and office artifacts.

Borrow:

- a clear task lifecycle and result panel;
- file change preview and artifact-first delivery;
- approachable skill discovery and task reuse.

Do not copy:

- unrestricted execution as the default;
- generic skill breadth before source admission, signatures, budgets, and rollback are proven.

Source: [WorkBuddy overview](https://www.workbuddy.cn/docs/workbuddy/Overview).

#### Feishu Knowledge Q&A

Feishu can answer from messages, documents, knowledge bases, and files the user is already allowed to access. Its official help explicitly states that retrieval does not exceed the questioner's existing permissions. This is the strongest domestic reference for zero-manual-import enterprise knowledge and permission-aware retrieval.

Borrow:

- identity-bound retrieval before ranking;
- organization-wide knowledge without repeated uploads;
- results that link back into the collaboration surface;
- admin-controlled knowledge Q&A and API access.

Anti-FOMO should integrate with this ecosystem rather than recreate messaging, docs, tables, and team collaboration.

Sources: [Feishu Knowledge Q&A](https://www.feishu.cn/hc/zh-CN/articles/854453754409-%E4%BD%BF%E7%94%A8%E7%9F%A5%E8%AF%86%E9%97%AE%E7%AD%94), [knowledge-base Q&A settings](https://www.feishu.cn/hc/zh-CN/articles/138181848717-%E8%AE%BE%E7%BD%AE%E7%9F%A5%E8%AF%86%E5%BA%93%E7%9A%84%E7%9F%A5%E8%AF%86%E9%97%AE%E7%AD%94%E5%8A%9F%E8%83%BD).

#### Kimi Deep Research

Kimi's official material describes intent clarification, a visible research plan, iterative search, source filtering, inline citations, long reports, interactive HTML, and Word/PPT/Excel/PDF output. Its help center publishes average process statistics, but those numbers remain vendor-reported and should not be treated as an independent benchmark.

This is the closest domestic threat to Anti-FOMO's report-generation experience. Kimi is stronger in immediate research breadth, user-visible progress, and polished multiform delivery. Anti-FOMO must be stronger in fixed-source repeatability, source acceptance, formal Chinese project documents, architecture tradeoffs, and acceptance proof.

Sources: [Kimi Deep Research feature page](https://www.kimi.com/zh-cn/features/deep-research), [Kimi Deep Research help](https://www.kimi.com/zh-cn/help/deep-research/deep-research-overview), [Kimi PPT](https://www.kimi.com/zh-cn/help/ppt/ppt-overview).

#### WPS AI and Baidu Wenku

WPS's advantage is native Office compatibility, collaborative editing, templates, and long-document reading with page-level click-back. Baidu Wenku has a broad content/template surface and editable AI PPT generation. Together they set the expected bar for visual polish and editable deliverables.

Borrow:

- native document editing after generation;
- style/template preservation and page-level source navigation;
- chart/table primitives rather than screenshot-like slides;
- Office roundtrip as a product feature, not only a test.

Do not compete on template volume. Anti-FOMO should make each editable block evidence-aware and stale-aware.

Sources: [WPS Office and AI](https://www.wps.cn/android), [WPS AI reading assistant](https://ai.wps.cn/introduction/assistanceReading), [Baidu Wenku AI PPT](https://wenku.baidu.com/ppt), [Baidu Qianfan PPT API](https://cloud.baidu.com/doc/qianfan/s/4mjcnolh6).

### 4.2 International products

#### NotebookLM / Gemini Notebook

The current official help goes beyond the earlier passive-notebook model. It supports source selection, citation hover and click-to-location, Drive synchronization, source discovery, Deep Research import, and experimental agentic actions that can create Word, Excel, PowerPoint, PDF, charts, images, and versioned artifacts.

This change removes much of the old differentiation from audio, mind maps, slides, and notebook chat. Anti-FOMO should borrow source-candidate review and citation UX, while keeping its stricter immutable revision, formal-document, and release-gate semantics.

Sources: [add or discover notebook sources](https://support.google.com/notebooklm/answer/16215270?hl=en), [use notebook chat and citations](https://support.google.com/notebooklm/answer/16179559?hl=en).

#### Notion AI

Notion Research Mode searches the workspace, connected applications, the web, PDFs, and databases, lets users select source classes, shows sources, supports follow-up, and saves the result as an editable page. Notion's structural advantage is that research lands directly in a collaborative system of pages, databases, permissions, comments, and automation.

Anti-FOMO should not build a Notion clone. It needs a block editor only for evidence-bound decision artifacts, then connector-based publication into the customer's existing workspace.

Source: [Notion Research Mode](https://www.notion.com/help/research-mode).

#### ChatGPT and Claude

ChatGPT Deep Research now publicly describes trusted-site restrictions, connected Apps/MCP, progress tracking, interruption, and refinement with new sources. ChatGPT Apps can search, sync, cite, and perform confirmed write actions. Claude Research combines web and connected internal sources, while Integrations use MCP to access and act in external tools.

These products make generic research orchestration and connector breadth difficult to defend. Anti-FOMO should expose comparable steering, but retain a domain-specific claim compiler and default-deny tool policy.

Sources: [OpenAI Deep Research](https://openai.com/index/introducing-deep-research/), [Apps in ChatGPT](https://help.openai.com/en/articles/11487775-connectors-in), [Claude Research](https://www.anthropic.com/news/research), [Claude Integrations and advanced research](https://www.anthropic.com/news/integrations).

#### Microsoft 365 Copilot, Perplexity, and Glean

Microsoft combines Copilot Notebooks with Researcher, source lists, editable Pages, Analyst, Designer, and native Office context. Perplexity combines web and organization files, inline file citations, projects, collaboration, connectors, admin controls, and file/app creation. Glean's strength is permissions-enforced search across many workplace systems and a company knowledge graph.

These are the primary references for enterprise connection, identity, and governance. Anti-FOMO should enter this layer through a small number of high-value read-only connectors, not a broad connector catalog.

Sources: [Microsoft 365 Copilot Researcher in Notebooks](https://support.microsoft.com/en-us/microsoft-365-copilot/use-researcher-in-microsoft-365-copilot-notebooks), [Perplexity Internal Knowledge Search](https://www.perplexity.ai/help-center/en/articles/10352914-what-is-internal-knowledge-search), [Glean enterprise search](https://www.glean.com/enterprise-search).

## 5. Gap analysis against the current `2.0.6` baseline

### 5.1 P0: release credibility, not another feature

The largest gap is that Anti-FOMO has acceptance calculators but not the real acceptance evidence. The following remain blocking:

- 300 human retrieval qrels and real parser cases;
- 60 expert formal-document samples;
- 100 independent report reviews and 500 entity-authenticity labels;
- real three-industry blind review and expert calibration;
- production permission and Skill security evidence;
- Office roundtrip and independent light/dark visual approval;
- production-like load, cost, queue recovery, backup restore, and external-volume failure evidence;
- named customer acceptance owners and signed decisions.

Without these artifacts, competitors can legitimately claim a better usable product even when Anti-FOMO has a stricter internal schema.

### 5.2 P0: research control and repeatability

Current competitors increasingly show planning, progress, source candidates, source selection, interruption, and multi-turn refinement. Anti-FOMO has backend evidence contracts but lacks a sufficiently clear operator experience for:

- editing and approving a research brief and question tree before spend;
- reviewing source candidates before admission;
- locking/rejecting sources and recording reasons;
- steering, pausing, resuming, or narrowing a running job;
- comparing two runs by source snapshot, plan, cost, claims, and output quality;
- reusing a verified source bundle without silently refreshing the web.

### 5.3 P0: measured retrieval and document parsing

BGE-M3 is now wired to the real Decision Studio path, but production quality is still unproven. Missing production evidence includes:

- human qrel-backed hybrid retrieval and reranking decisions;
- layout/table/formula/image parsing across representative Chinese Office/PDF documents;
- benchmark-based parser routing and explicit degradation;
- source drift and stale-index monitoring;
- latency, memory, disk, and cost envelopes for local and hosted strategies.

### 5.4 P1: editable, evidence-aware artifact quality

Competitors increasingly create polished, editable outputs. Anti-FOMO's schema-first artifacts are directionally stronger for governance but weaker as a daily editing surface. It needs:

- block-level editing that preserves claim and source lineage;
- comments, approvals, versions, and field-level stale indicators;
- editable charts/tables with deterministic data bindings;
- robust WPS/Microsoft Office/LibreOffice roundtrip;
- partial regeneration that preserves human edits outside the affected dependency graph;
- customer-ready templates without internal compiler or diagnostic language.

### 5.5 P1: real enterprise identity, connectors, and collaboration

The ACL and connector contracts exist locally, but no production connector makes them useful. Missing capabilities include:

- OIDC/OAuth/SSO and tenant administration;
- source-native ACL synchronization before retrieval;
- deletion, revocation, and source-move propagation;
- read-only Feishu/Tencent Docs/Notion/Microsoft 365 pilots;
- review assignment, notifications, and publication backflow;
- audit export, retention, legal hold, and customer deployment controls.

### 5.6 P1: durable agent operations

The governed Skill registry is a strong contract, but it is not yet a production operations system. It still needs:

- durable runs, checkpoints, retry policy, and resume after process restart;
- approval steps for source admission, spend, writes, and external actions;
- schedule, concurrency, budget, timeout, and cancellation controls;
- replay and rollback tied to immutable inputs and outputs;
- production signing keys, rotation, revocation, and benchmark evidence;
- a small set of proven first-party Skills before any marketplace.

### 5.7 P2: vertical evidence and commercial packaging

Generic web research cannot reliably support consulting-grade outputs. Anti-FOMO needs governed official and licensed source packs for healthcare, finance, and culture-tourism, plus enterprise packaging such as onboarding, deployment, backup, monitoring, support, billing, and service-level objectives.

### 5.8 SWOT summary

| Dimension | Assessment |
| --- | --- |
| Strengths | Distinct WeChat-heavy intake, fail-closed evidence admission, immutable source/claim lineage, Chinese formal-document contracts, architecture tradeoff engineering, and executable acceptance evidence in one local-first workflow |
| Weaknesses | Release claims are not yet backed by the required real human artifacts; research steering, parser/retrieval benchmarks, editing quality, production connectors, and team operations trail mature suites |
| Opportunities | Chinese organizations need auditable research and project documents that connect policy, evidence, calculations, architecture decisions, and acceptance; this is poorly served by generic chat and AIPPT products |
| Threats | Deep research and artifact generation are rapidly commoditizing; suite vendors own identity/content graphs; poor first-run output can erase trust before stricter backend governance becomes visible |

## 6. Open-source and model reuse assessment

| Candidate | Useful capability | Recommended use | Boundary before adoption |
| --- | --- | --- | --- |
| [Docling](https://github.com/docling-project/docling) | Multi-format parsing, layout/table/formula understanding, coordinates, lossless document model, local execution | First shadow parser and parser-regression reference | Pin code/model revisions; benchmark Chinese samples; keep existing fallback; review every model license |
| [MinerU](https://github.com/opendatalab/MinerU) | Strong Chinese/scanned/complex-document parsing, tables, formulas, OCR, visual QA | Isolated second parser for difficult-document A/B and benchmark generation | Its repository license has additional conditions; keep outside the default commercial bundle pending legal review |
| [Open Deep Research](https://github.com/langchain-ai/open_deep_research) | Configurable model/search/MCP research graph, plan/execute patterns, 100 bilingual research tasks | Reuse evaluation and orchestration ideas; map them to the existing workflow protocol | Do not replace evidence admission, Claim Graph, or cost controls; reproduce benchmark locally |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Parser choices, chunk visualization, hybrid recall/reranking, citations, connectors, agent workflows | UX and benchmark reference; optional isolated interoperability experiment | Do not migrate the platform wholesale; it would duplicate current domain contracts and add operational weight |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | Local/global/DRIFT graph-query patterns | Benchmark selected graph-query strategies against the existing Claim Graph | Indexing is resource-intensive; no production switch without qrel and cost wins |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Evidence gathering, document metadata, citation/retraction-oriented scientific workflow | Borrow source-quality and citation-evaluation patterns for research packs | Scientific assumptions do not directly transfer to Chinese policy/procurement documents |
| [Qwen3 Embedding/Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-8B) | Multilingual, instruction-aware embedding/reranking in multiple sizes | Shadow candidate against the installed BGE-M3 path, starting with the smallest viable reranker | Do not assume the 8B model fits local latency/memory; select by qrels, cost, license, and hardware evidence |

Adoption rule:

`quarantine -> license/provenance snapshot -> pinned revision -> security scan -> representative benchmark -> shadow run -> rollback proof -> limited rollout`

No open-source component may bypass source admission, ACL prefiltering, Claim Graph validation, or immutable release evidence.

## 7. Optimized post-2.0.6 roadmap

### 7.1 Sequencing rule

The roadmap remains gate-driven for promotion. The user explicitly authorized implementation through `2.2.0` on a non-release development branch, so later engineering contracts now exist while commercial promotion still requires every earlier named evidence gate to pass for an immutable build digest.

| Version | Priority | Outcome | Start condition |
| --- | --- | --- | --- |
| `2.0.7` | P0 | Release Evidence Closure | Starts now; feature freeze |
| `2.1.0` | P0 | Research Control Room | `2.0.7` evidence complete or explicit non-release research branch approval |
| `2.1.1` | P0 | Retrieval and Parsing Quality | Control-room source/run contracts stable |
| `2.1.2` | P1 | Evidence-Aware Decision Document Editor | Retrieval/citation coordinates meet production gate |
| `2.1.3` | P1 | Enterprise Identity and Connectors | ACL matrix passes before any customer connector pilot |
| `2.1.4` | P1 | Governed Agent Operations | Production signing, approval, and rollback contracts pass |
| `2.1.5` | P1 | Vertical Evidence Packs | Core platform release evidence and source licensing are ready |
| `2.2.0` | P0 commercial | Team Decision OS release candidate | At least one complete vertical pilot and all inherited gates pass |

### 7.2 `2.0.7`: Release Evidence Closure

Goal: convert the existing `2.0.1-2.0.6` calculators into a complete, independently reviewable release-candidate evidence bundle. No broad feature work is permitted in this version.

Delivery:

- Freeze a release-candidate digest covering code, migrations, model/parser policies, prompts, schemas, fixtures, and UI baseline.
- Complete the 300 human qrels, 100 real parser samples, 60 expert formal-document samples, 100 independent report reviews, and 500 entity labels.
- Complete real expert calibration, three-industry blind review, and named customer acceptance.
- Run production permission/Skill matrices, Office roundtrip, light/dark visual review, load/cost tests, queue recovery, backup restore, audit export, and external SSD failure injection.
- Expose missing owner, stale artifact, reviewer conflict, and invalid evidence directly in the release console.
- Fix only defects discovered by these runs; every fix creates a new RC digest and reruns affected suites.

Exit gate:

- Every inherited human, expert, customer, Office, visual, security, performance, recovery, and Decision Studio suite passes against the same immutable RC digest.
- Low-quality invalid payload count is `0`; flagged rate is `<=10%`; no hard failure is hidden by an aggregate score.
- Independent reviewer identities, raw artifact URIs, attestations, hashes, and timestamps are complete.
- Synthetic fixtures remain test evidence only and are excluded from release approval counts.

### 7.3 `2.1.0`: Research Control Room

Goal: make professional research steerable, repeatable, and inspectable before and during model spend.

Delivery:

- Structured research brief with goal, audience, decision, region, time range, source policy, exclusions, deliverables, budget, and acceptance criteria.
- Editable question tree and plan approval before execution.
- Source candidate inbox with preview, trust indicators, accept/reject/lock decisions, and reason codes.
- Live plan/progress/cost view with pause, cancel, resume, narrow, and add-source controls.
- Immutable reusable source bundles and explicit `refresh / reuse frozen snapshot` choice.
- Run comparison across plan, source set, query trace, claims, contradictions, cost, latency, and artifact delta.

Exit gate:

- In at least 30 representative tasks, `>=95%` of approved plan edits are respected by execution.
- Excluded or rejected source leakage is `0` across retrieval, claims, exports, and regenerated artifacts.
- Pause/resume and process-restart recovery preserve source snapshot, budget, accepted claims, and audit history.
- Every generated section maps to an approved question or is explicitly marked supplementary.

### 7.4 `2.1.1`: Retrieval and Parsing Quality

Goal: establish a measured production retrieval/parser stack rather than selecting models by reputation.

Delivery:

- Hybrid sparse+dense retrieval, query decomposition/rewriting, metadata filters, and a shadow reranker lane.
- BGE-M3 remains the incumbent; Qwen3 and other candidates compete on the same human qrels and hardware/cost envelope.
- Docling shadow parser plus isolated MinerU difficult-document lane; deterministic parser routing by format and benchmark class.
- Element-level coordinates for text, table cells, formulas, images, and OCR spans.
- Source drift, parser regression, stale index, model revision, latency, memory, and cache-volume monitoring.

Exit gate:

- Expand to at least 600 adjudicated qrels, balanced across healthcare, finance, culture-tourism, tables/numbers, cross-page questions, and hard negatives.
- `nDCG@10 >=0.82`, `Recall@20 >=0.92`, and critical cross-industry false positive `<=1%`; every change must beat or tie the incumbent within the cost envelope.
- Citation click-back accuracy is `>=99%` on at least 200 representative documents; unsupported coordinates fail closed.
- Parser routing beats the best single-parser baseline on the locked corpus without an unexplained P95 latency or memory regression above `30%`.

### 7.5 `2.1.2`: Evidence-Aware Decision Document Editor

Goal: close the usability gap with WPS, Microsoft 365, Kimi, and Notion while preserving evidence lineage.

Delivery:

- Structured block editor for research reports, solutions, feasibility studies, project proposals, and executive decks.
- Side-by-side source passage, claim state, counter-evidence, formula, assumption, policy, owner, and review status.
- Human-edit preservation across partial regeneration and dependency-based stale propagation.
- Editable data tables and charts bound to deterministic calculation sheets.
- Version history, comments, approval, section compare, and publish snapshot.
- WPS/Microsoft Office/LibreOffice template and roundtrip profiles.

Exit gate:

- Unsupported generated numbers are `0`; formula/export consistency and critical claim citation coverage are `100%`.
- At least `99%` of edits outside an affected dependency subgraph survive partial regeneration.
- Locked Office corpus passes text, table, chart-data, style, pagination, and editability checks; independent light/dark and document visual review passes.
- Three document classes each receive at least 20 blind expert reviews with no critical formal-contract omission.

### 7.6 `2.1.3`: Enterprise Identity and Connectors

Goal: make Knowledge Spaces useful inside existing enterprise systems without weakening ACL or evidence rules.

Delivery:

- OIDC/OAuth/SSO, tenant administration, service accounts, and role mapping.
- Read-only pilots for Feishu, Tencent Docs, Notion, and Microsoft 365/SharePoint; writeback remains separately approved.
- Incremental sync, source-native ACL labels, revocation/deletion propagation, cursor recovery, and provenance.
- Publication backflow with preview, destination permission check, and immutable source/artifact link.
- Retention, audit export, credential rotation, and connector health operations.

Exit gate:

- Permission leakage is `0` across search, chat, cache, citation click-back, export, deep link, and connector writeback tests.
- Revocation and deletion meet a documented customer SLA and cannot leave a critical claim eligible for new artifacts.
- Connector credentials appear `0` times in logs, prompts, traces, exports, and model-provider payload snapshots.
- Each production pilot completes restore, replay, duplicate, move, rename, partial failure, and rate-limit tests.

### 7.7 `2.1.4`: Governed Agent Operations

Goal: turn the Skill contract into reliable long-running operations with human control.

Delivery:

- Durable runs, checkpoints, idempotency, retries, cancellation, resume, schedules, queues, concurrency, and budgets.
- Approval nodes for source admission, spend increases, external writes, destructive actions, and release promotion.
- Production key management, signature rotation, revocation, package transparency log, and rollback.
- Dry-run diff for file/database/connector effects; immutable replay with model/tool revision disclosure.
- First-party Skills only: research orchestration, formal-document intake, evidence/entity audit, architecture validation, and release evidence collection.

Exit gate:

- Undeclared network, file, database, connector, or release action count is `0` across at least 100 prompt-injection and confused-deputy cases.
- Every high-risk action has an authenticated human approval linked to exact inputs and effects.
- Restart/failure tests recover without duplicate external effects or corrupted evidence chains.
- Skill benchmark, cost, permissions, license, signature, and rollback evidence are complete before approval.

### 7.8 `2.1.5`: Vertical Evidence Packs

Goal: build domain defensibility that generic deep-research products do not provide by default.

Delivery:

- Healthcare, finance, and culture-tourism source registries covering official policy, procurement, regulatory, corporate disclosure, and approved licensed sources.
- Versioned sector ontology, entity roles, document contracts, formulas, risk rules, hard negatives, and source-quality policies.
- Sector-specific question trees, claim checks, architecture patterns, acceptance criteria, and expert review rubrics.
- Source licensing, retention, citation, redistribution, and expiry controls.

Exit gate:

- Each sector has at least 100 locked benchmark tasks and 30 real expert-reviewed artifacts.
- Official/approved source coverage for critical claims is `>=95%`; critical entity precision is `>=98%`; cross-industry leakage is `0`.
- Every policy or licensed-data update produces correct stale impact and bounded rebuild behavior.
- At least one named pilot owner per sector approves the source pack and review rubric.

### 7.9 `2.2.0`: Commercial Team Decision OS

Goal: release a team product for evidence-bound decisions, not a generic AI workspace.

Delivery:

- Multi-user projects, review queues, assignments, notifications, decision register, portfolio search, and reusable approved evidence packs.
- Deployment profiles, encryption, secrets, retention, backup/restore, disaster recovery, observability, support bundle, billing/metering, and SLA reporting.
- Customer onboarding, migration, administrator controls, audit export, model/data policy, and incident procedures.
- Three complete pilot workflows: one each for healthcare, finance, and culture-tourism.

Commercial exit gate:

- All inherited gates from `2.0.7-2.1.5` pass for the release digest.
- At least three real customer pilot projects complete source intake, research, formal artifact delivery, architecture/acceptance evidence, and signed outcome review.
- No critical security, permission, evidence, Office, visual, recovery, or customer-acceptance issue remains open.
- Release readiness reports `ready` without manual override; otherwise the product remains a development or pilot build.

## 8. Portfolio priorities and non-goals

### Invest

- Evidence closure and independent validation.
- Research steering and frozen-source reproducibility.
- Retrieval/parser quality measured on Chinese professional documents.
- Formal decision-document editing with claim/formula/policy lineage.
- A few identity-aware connectors and vertical evidence packs.
- Governed execution tied to approval and acceptance evidence.

### Integrate

- Feishu, Tencent Docs, Notion, Microsoft 365, WPS, and customer systems of record.
- Open-source parsers and retrieval components only through shadow benchmarks.

### Do not build now

- A general-purpose Notion/Feishu clone.
- A broad public Skill marketplace.
- A generic AI PPT or template marketplace.
- An unrestricted desktop agent.
- A social/public knowledge square.
- Model switching marketed as quality improvement without qrel and artifact evidence.

## 9. Product-level north-star and guardrails

North-star metric:

`percentage of customer decisions that reach approved evidence-bound artifact plus executable acceptance evidence without critical rework`

Supporting metrics:

| Layer | Metric |
| --- | --- |
| Research | approved-plan conformance, source acceptance precision, frozen-run reproducibility, useful claim yield |
| Retrieval | nDCG@10, Recall@20, hard-negative rate, citation-coordinate accuracy |
| Documents | unsupported numbers, formal-contract omissions, edit preservation, Office roundtrip |
| Decisions | critical claim coverage, unresolved contradiction rate, ADR/QAW/test traceability |
| Operations | unauthorized actions, ACL leakage, recovery time, duplicate effects, audit completeness |
| Customer | expert deliverability, critical rework rate, acceptance cycle time, signed pilot outcome |

Guardrail: model fluency, report length, number of sources, or visual polish can never override evidence, permission, formal-contract, or acceptance hard failures.

## 10. Roadmap governance

- This document is a research snapshot. Re-run the official-source scan before each major-version planning boundary because competitor capabilities change quickly.
- Each version receives a short architecture decision record stating what is built, integrated, deferred, and explicitly not copied.
- Every claimed competitor-inspired improvement must map to a customer problem and a measurable acceptance gate.
- If `2.0.7` remains blocked, status stays blocked. Later planning may continue, but commercial promotion and broad feature claims do not.
