# Anti-FOMO Project Memory

Last updated: 2026-06-21 (Asia/Shanghai)

This is the compressed handoff context for continuing Anti-FOMO in a new chat.
Treat the repository and current tests as the source of truth when this file
conflicts with old planning documents.

## New Chat Starter

Use this prompt in the next window:

```text
请继续开发 /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo。

先完整阅读项目根目录 memory.md，再按其中的“当前真实状态、未完成事项、架构边界和开发约束”核对代码与 Git 状态。

当前正式版本是 1.8.0+20260622，主分支 main；检出后用 `git rev-parse v1.8.0+20260622` 核对发布提交。
LangGraph 是默认研究工作流，deterministic 是必须保持可用的回滚路径。

最新完成的产品开发切片：
1. 全部 15 个主界面已做语义深色模式审计，生成 30 张日/夜截图；分析进度卡和知识库嵌套白色面板已修复；
2. 手动微信收藏导入批次持久化与前端轮询恢复已修复；
3. 已增加可选 wechat-cli 收藏自动导入适配器，但本机未安装 wechat-cli，设置页应显示 unavailable；不得自动安装、重签名或提权；
4. 微信正文提取会拒绝参数错误/验证/失效壳页；
5. 研报、可研和项目建议书已增加多视角研究、交叉验证、方案比选、运营、影响、证据矩阵与自审修订；
6. OpenAI 旧适配器的额度异常已修复；主凭据额度耗尽后配置的 fallback credential 可正常接管，dry-run 当前 provider_used=openai、model=gpt-5.5。
7. `1.8.0` 专业报告质量线已插队成为下一版本；P0.1/P0.2/P0.3/P1.1/P1.2/P1.3/P2.1/P2.2/P2.3/P2.4/P2.5/P2.6/P2.7 已本地实现：网页污染会阻断通过，只有章节结构但没有具体证据锚点的文档不能再拿 pass，语义挑战者会阻断范围漂移、跨章节实体/数字冲突和黄金样本对齐不足，四类交付文档已拆成专用编译器，并已加入量化决策模型、3 个真实业务主题黄金样本验证、正式导出的受控版式/编号/表格/页眉页脚、原生 DOCX、受控 PDF 往返诊断、可编辑 PPTX、中文校对、截图视觉回归指纹、专业模板占位、非 GUI Office 往返结构校验、真实数据图表资产清单、可替换图片资源、客户品牌模板、受控 headless 渲染策略、DOCX 复杂样式模板、PPTX 原生可编辑图表对象、嵌入 workbook、Office 打开验证门禁、DOCX/PPTX 原生图片 media part、PDF 矢量品牌框架、PDF 原生 Image XObject 和真实业务样本 artifact 批量视觉基线。

下一步优先：
1. 继续 `1.8.0` P2 正式交付工程下一切片：P2.7 已补 PDF 原生图片对象、LibreOffice 可配置路径探测、代表性 GUI 打开门禁和新一轮 artifact baseline；下一步如需真正 Office→PDF headless 转换，需要修复 Homebrew/GitHub 网络后安装 LibreOffice，或手动设置 `ANTI_FOMO_LIBREOFFICE_CLI=/Applications/LibreOffice.app/Contents/MacOS/soffice`；
2. 对 P1.3 三个真实业务主题继续补人工证据锚点与专家盲评，状态仍是 `draft_for_blind_review`；
3. 让用户在 Safari 实测深色模式、微信收藏导入和实际研报；
4. 评测集 1.2.0 的独立确认仍需外部专家完成；未获预算批准前不要运行付费全量评测；
5. 审阅当前未提交条目，未经明确要求不要提交、打 tag 或推送。

不要读取、输出或提交 backend/.env、私有小程序配置、数据库、备份库、评审者个人信息和 .tmp 运行产物。
未经我明确要求，不要自动提交、打 tag、推送 GitHub/ModelScope，也不要运行会产生模型费用的完整真实评测。
```

## 1. Canonical Repository

Canonical working repository:

```text
/Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
```

Current Git truth:

- Branch: `main`
- HEAD: `6783a9a7f536078c980ccdda888883fcdf7b32ff`
- Commit: `Apply expert scope feedback to evaluation set`
- Tag: `v1.8.0+20260622`
- Package version: `1.8.0`
- `origin/main`: synchronized, ahead/behind `0/0`
- `modelscope/main`: synchronized, ahead/behind `0/0`
- Worktree was unified into the `1.8.0+20260622` release commit; after checkout
  it should be clean except for ignored local runtime files.
- Remotes:
  - GitHub: `https://github.com/ChrisChen667788/antifomo.git`
  - ModelScope: `https://www.modelscope.cn/models/haozi667788/antifomo.git`

Do not continue development in these copies:

- `/Users/chenhaorui/Documents/antifomo`
  - Small public/sparse copy, not the full current development tree.
- `/Users/chenhaorui/anti-fomo-extension-chrome`
- `/Users/chenhaorui/Desktop/AntiFomoChromePlugin`
  - Standalone extension artifacts, not the canonical monorepo.

## 2. Product Definition

Anti-FOMO is a local-first, open-source AI research and delivery workspace.
Its core loop is:

```text
collect -> clean -> triage -> research -> compare -> focus -> action -> delivery
```

Primary users:

- Solution architects
- Industry consultants
- Presales / BD / strategy teams
- Product and research leads
- Users monitoring WeChat-heavy and public-source information flows

The product must not be described as only:

- a bookmark manager
- a read-later queue
- a generic AI summarizer
- a WeChat scraper

The actual product story is:

```text
WeChat/public signals
  -> normalized evidence
  -> research and comparison
  -> architecture readiness/workbench
  -> focus and follow-up actions
  -> client-ready advisory delivery
```

## 3. Product Boundaries and Non-Goals

Hard boundaries:

- No paywall bypass.
- No login-wall bypass.
- No unauthorized private/back-office data collection.
- No claim that a related tender is the exact target project without evidence.
- No claim that offline LangGraph parity proves live retrieval or answer quality.
- No live-provider evaluation without independent review and approved budget.
- No secrets, reviewer PII, private miniapp config, local databases, or local
  evaluation artifacts in public commits.
- Unrelated research reports and personal deliverables should be exported to
  `/Users/chenhaorui/Downloads`, not added to this repository.

WeChat collection policy:

- Headless/source collector is the primary reliable daily source path.
- WeChat PC Agent is a supplementary URL discovery and recovery path.
- Directly reading or reverse-engineering personal WeChat local databases is not
  the default product path.
- WeChat Favorites import uses exported HTML/TXT, clipboard, shortcut files,
  and raw/escaped/encoded `mp.weixin.qq.com` links.

WorkBuddy policy:

- Tencent CodeBuddy CLI is installed locally.
- The app can detect CLI installation/authentication and use it after login.
- Without authenticated official CLI/gateway, the system uses the local
  compatibility adapter.
- This is not personal-WeChat account hosting.

## 4. Current Technology Stack

Frontend:

- Next.js `16.2.9`
- React / React DOM `19.2.3`
- TypeScript 5
- Tailwind CSS 4
- Vitest 4 + Testing Library + jsdom
- Semantic `af-*` theme tokens with light/dark production screenshots

Backend:

- Python + FastAPI
- SQLAlchemy
- Alembic migrations
- SQLite local default; PostgreSQL-compatible database URL supported
- Pydantic DTOs
- Pytest

Research/model runtime:

- Framework-neutral research workflow protocol
- LangGraph `StateGraph` is the production default
- Deterministic workflow engine is the immediate rollback
- `langgraph_shadow` remains a compatibility alias
- Replaceable LangChain OpenAI structured-output adapter
- Mock provider remains the zero-cost default
- Provider token usage and model cost ledger are supported
- Optional CrossEncoder/SentenceTransformers reranker

Other surfaces:

- WeChat Mini Program shell in `miniapp/`
- Chrome extension in `browser-extension/chrome/`
- Collector/WeChat/watchlist/evaluation automation in `scripts/`

## 5. Main User Surfaces

Web routes:

- `/` - feed signal dashboard and swipe triage
- `/inbox` - URL/text intake, research generation, report delivery
- `/items/[id]` - item detail, feedback, reprocess, interpretation
- `/saved` - saved/read-later content
- `/focus` - focus session and Focus Assistant
- `/session-summary` - session outputs and exports
- `/collector` - collector entry surface
- `/settings` - preferences, models, WorkBuddy, collector operations
- `/research` - research center/control plane
- `/research/topics/[id]` - topic workspace and version comparison
- `/research/compare` - compare workspace
- `/research/archives/[id]` - markdown archive viewer
- `/knowledge` - knowledge library
- `/knowledge/accounts` - account/commercial intelligence
- `/knowledge/merge` - knowledge merge workflow

## 6. Current Capability Inventory

### Intake and triage

- URL, text, RSS, newsletter, file, YouTube transcript intake
- Browser extension capture
- WeChat Favorites preview/import
- Multi-file `.url` / `.webloc` import
- Raw, HTML-entity, JSON-escaped, and percent-encoded WeChat URL handling
- Persistent import batches and latest unfinished queue recovery
- Ready/processing/failed/done counters
- Failed-item batch retry
- Left swipe/Ignore and right swipe/Save, with automatic next card
- Processed cards are removed from the active import queue

### Collector operations

- Source/feed management
- Headless source collector daemon
- WeChat PC Agent supplementary intake
- OCR preview and fallback
- URL-first article extraction
- Deduplication and pending recovery
- Run/batch status and route-quality diagnostics
- Per-source health, coverage, body success, poor/watch source counts
- Daily collector report and queue operations

### Research and retrieval

- Keyword research and structured report generation
- Follow-up research and affected-section diagnostics
- Topic tracking, report versions, archive history, compare snapshots
- Persistent retrieval index with resumable rebuild
- Stable chunk IDs, sentence-window chunks, parent/section links
- Section-level retrieval packs
- Official-source bias and optional reranking
- Corrective retrieval and weak-evidence expansion
- Source diagnostics and unsupported-claim detection

### Research quality and experiments

- Research readiness and quality profiles
- Grounding/citation/target-account/section evidence diagnostics
- Delivery quality self-review and deterministic self-repair
- Query/routing/reranker experiment control plane
- Frozen cohorts and locked baselines
- Gate history, rollout manifests, activation/revocation
- Active policy registry and runtime strategy snapshot
- Runtime config injection into real report generation

### Advisory delivery

- Three-year tender/product/technical-parameter intelligence
- Feasibility study and project proposal
- Client-facing PPT outline
- Client brief, bidding memo, execution materials
- Architecture readiness scoring
- Architecture blueprint:
  - business/role layer
  - application capability layer
  - model/data/integration layer
  - security/deployment/operations layer
- Solution architect workbench:
  - customer scenarios
  - stakeholder concerns/questions
  - decision criteria
  - capability-to-architecture matrix
  - ADR-style decisions
  - integration dependency diagnostics
  - validation actions
  - next-meeting agenda

### Execution and knowledge

- Focus sessions and summary generation
- Reading list, todo draft, executive brief, sales brief, outreach draft
- Watchlists, run history, failed-run retry notes, digest export
- Knowledge library and merge workflow
- Account intelligence and opportunity summaries
- Commercial follow-up and review queues

## 7. Architecture Ownership Rules

Backend allowed dependency direction:

```text
api -> application/orchestration -> domain owners -> persistence/infrastructure
```

Rules:

- API routers own HTTP concerns, not domain policy.
- New research behavior must enter an owner module and be injected through
  workflow/runtime dependency ports.
- `backend/app/services/research_service.py` is a compatibility/dependency
  wiring facade only.
- Do not put new domain implementations back into the research facade.
- Delivery owner modules must not import API routers or the solution
  orchestration parent.
- Keep public API and persistence behavior stable unless explicitly versioned.
- Extract modules only when there is a stable responsibility and testable
  contract; line count alone is not a reason to split.

Important backend owners:

- WeChat Favorites parsing:
  `backend/app/services/collector_imports/wechat_favorites.py`
- Collector route owners:
  `backend/app/api/collector_*.py`
- Market intelligence:
  `backend/app/services/delivery/market_intelligence.py`
- Solution architecture:
  `backend/app/services/delivery/solution_architecture.py`
- Delivery materials:
  `backend/app/services/delivery/solution_materials.py`
- Research workflow:
  `backend/app/services/research/generation_workflow.py`
- Workflow protocol/deterministic engine:
  `backend/app/services/research/workflow_engine.py`
- LangGraph engine:
  `backend/app/services/research/langgraph_workflow_engine.py`
- Workflow parity:
  `backend/app/services/research/workflow_parity.py`
- Evaluation dataset:
  `backend/app/services/research/evaluation_dataset.py`
- Evaluation review:
  `backend/app/services/research/evaluation_review.py`
- Evaluation budget:
  `backend/app/services/research/evaluation_budget.py`
- Run metrics:
  `backend/app/services/research/run_metrics.py`

Frontend rules:

- `src/app` files remain route shells.
- Feature state belongs in focused controllers/hooks.
- Pure derived behavior belongs in model/view-model helpers.
- API clients and DTOs remain split by domain under `src/lib/api/`.
- `src/lib/api.ts` is a compatibility facade, not a place for new broad logic.
- New UI must prefer semantic `af-*` theme tokens.
- Do not reintroduce hard-coded day-only white/slate status surfaces.

## 8. Historical Development Timeline

### Initial prototype - 2026-03-16

The first implementation was a Next.js/Tailwind demo with:

- Feed
- Inbox
- Item detail
- Focus timer
- Session Summary
- Mock data and componentized UI

This initial work was created under `/Users/chenhaorui/Documents/New project`
and later evolved/migrated into the current canonical repository.

### `0.3.x`

- Research compare/export baseline
- Archive snapshots
- Offline metrics
- Evidence gates and section evidence packs
- Industry methodology playbooks

### `0.4.x`

- Persistent retrieval index
- Section routing
- Golden report evaluation
- Tender/product intelligence
- Feasibility/project proposal/PPT delivery
- Follow-up diagnostics and scenario refresh

### `0.5.x`

- CRAG-style retrieval correction
- Grounding review and report self-evaluation
- Schema-v2 chunks and stable chunk IDs
- Source cleaning and entity quality
- Initial reranker controls

### `0.6.0` - `0.6.4`

- CrossEncoder adapter and fallback
- Advisory-grade delivery artifacts
- Quality-triggered public-source expansion
- Delivery quality scoring and self-repair
- Diagnostics control plane and regression metrics

### `0.6.5` - `0.6.10`

- Persistent experiment plans
- Frozen cohorts and locked baselines
- Rollout gates/manifests
- Active policy registry
- Runtime strategy snapshots
- Retrieval and generation runtime strategy activation

### `0.6.11`

- Release-grade README/docs/screenshots
- Screenshot quality gates and manifest
- Feature/release capability maps

### `0.7.0`

- Focus collector reliability
- Headless-source-first startup
- WeChat PC Agent retained as supplementary intake
- Per-source health and omission diagnostics

### `0.8.0`

- Solution architecture readiness
- Architecture blueprint
- NFRs, integration risks, assumptions
- Stakeholder questions and validation actions

### `0.8.1`

Built through the 2026-05-18 to 2026-05-20 iteration:

- WeChat Favorites import and preview
- URL normalization/deduplication
- Mixed link/text export parsing
- Multi-file shortcut import
- Persistent import batches
- Queue recovery and failed-item retry
- Homepage swipe triage and queue removal

### `0.9.0`

- Solution architect workbench
- Customer scenarios
- Stakeholder maps
- Decision criteria
- Validation actions
- Next-meeting agenda
- Markdown export and report-card UI

### `1.0.0`

- Completed local-first WeChat-to-solution baseline
- Connected intake, triage, evidence research, architecture readiness,
  workbench output, migrations, docs, and regression validation

### `1.1.0`

- Large modular architecture refactor
- Collector route decomposition
- Research owner packages and dependency seams
- Feature API clients and DTO contract splits
- Research Center/controller decomposition
- Collector Ops/controller decomposition
- Report, knowledge, and session panel decomposition
- Semantic theme token baseline

### `1.1.1`

- Framework-neutral research workflow
- Per-run metrics and cost ledger
- Versioned 100-case evaluation structure

### `1.2.0`

- LangChain structured-output adapter
- Provider token usage
- Configurable pricing
- Independent generation/strategy model routing

### `1.2.1`

- Provider owner split
- Persisted research-job metrics/cost ledger
- Typed metrics API
- CI secret scanning

### `1.3.0`

- Executable 100-case evaluation runner
- Bounded case selection
- Machine-readable artifacts
- Honest unavailable retrieval metrics
- Strict release-gate eligibility

### `1.4.0`

- Opt-in LangGraph shadow runtime
- Same framework-neutral owner ports
- No automatic production dual-run cost

### `1.5.0`

- Backend hotspot owner extraction
- Frontend model owner extraction
- Vitest/Testing Library regression baseline
- Next.js upgrade to `16.2.9`

### `1.6.0`

- Shared Focus runtime owner
- Pre-hydration preference bootstrap
- 15 light + 4 dark production screenshots
- Dark-mode compatibility layer
- Removal of 40 dead research facade wrappers

### `1.7.0`

- Locked 100-case evaluation set
- 100/100 deterministic/LangGraph offline parity
- LangGraph promoted to production default
- Deterministic engine retained as rollback
- PostCSS overridden to `8.5.15` while Next.js stable pins an older version

### `1.7.1`

- Independent review export/finalize/validate workflow
- Immutable locked-context checks
- Review attestation and content digest
- Live-evaluation budget planning
- Default maximum of five live cases per invocation
- Runtime stop on missing pricing or budget overrun

### `1.7.2`

- Processed expert scope feedback:
  - 21 cases directly approved
  - 78 cases required region and/or named-subject correction
  - 1 case (`transport-003`) unanswered but already concrete
- Only `regions`, `entities`, and curation provenance changed
- Expected behavior, answer terms, and source domains were preserved
- Dataset upgraded to `1.2.0`
- New locked digest:
  `f52835846045726158277abf5212dda8370d3b23d4b17229df161b827e514df5`
- All broad/empty national/global region scopes removed

## 9. Current Validation Baseline

Latest P2.7 validation on 2026-06-22:

- P2.6 full `npm run check` passed before P2.7
  - ESLint passed
  - 16 frontend tests passed
  - production build passed
  - 345 backend tests passed
- P2.7 targeted `backend/tests/test_formal_document_rendering.py` passed `10/10`.
- P2.7 artifact baseline generated all 3 real-business samples:
  `/tmp/af-p27-real-business-baseline/visual-baseline-manifest.json`
  - 3 samples
  - 9 artifacts
  - `failed_validation_count=0`
  - `failed_quicklook_count=0`
  - PDFs all expose `has_vector_layout=True` and `has_native_image=True`
- Independent P2.7 roundtrip manifest:
  `/tmp/af-p27-real-business-baseline/roundtrip-manifest.json`
  - DOCX/PPTX all expose `native_images=True`
  - PPTX all expose `native_editable_charts=True`
  - PDFs all expose `has_vector_layout=True` and `has_native_image=True`
  - LibreOffice conversion remains `skip_no_libreoffice`
- Representative GUI open gate passed:
  `/tmp/af-p27-real-business-baseline/gui-open-manifest.json`
  - opened `shanghai-medical-ai-2026` DOCX in Microsoft Word
  - opened PPTX in Microsoft PowerPoint
  - opened PDF in Preview
  - all returned `gui_open.status=launched`; human visual polish still requires
    the user to inspect the opened windows
- LibreOffice installation attempt:
  - `brew install --cask libreoffice` failed during Homebrew API download and was
    terminated after hanging
  - retry with `HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_FROM_API=1` failed
    cloning `https://github.com/Homebrew/homebrew-core/` due HTTP2 framing error
  - code now detects `ANTI_FOMO_LIBREOFFICE_CLI`, `LIBREOFFICE_CLI`,
    `SOFFICE_PATH`, `/Applications/LibreOffice.app/Contents/MacOS/soffice`,
    `/opt/homebrew/bin/soffice`, `/usr/local/bin/soffice`, then PATH
- P2.6 targeted backend validation passed `28/28`:
  `backend/tests/test_formal_document_rendering.py`,
  `backend/tests/test_research_solution_delivery_exports.py`,
  `backend/tests/test_daily_brief_and_extended_tasks.py`,
  `backend/tests/test_delivery_quantitative_models.py`,
  `backend/tests/test_delivery_document_compilers.py`,
  `backend/tests/test_real_business_delivery_golden_samples.py`
- P2.3 targeted backend validation passed `20/20`
- P2.4 targeted affected backend validation passed `25/25`
- P2.5 targeted affected backend validation passed `25/25`
- P2.6 historical artifact visual baseline generated all 3 real-business samples:
  `/tmp/af-p26-real-business-baseline/visual-baseline-manifest.json`
  - 3 samples
  - 9 artifacts: feasibility DOCX, solution PPTX, project-proposal PDF per sample
  - 0 validation failures
  - 0 PDF QuickLook failures
  - manifest includes raw `sha256`, stable `normalized_sha256`, preview hash,
    visual fingerprint, OpenXML/PDF validation, and PDF thumbnail fingerprint
- Independent P2.6 roundtrip manifest:
  `/tmp/af-p26-real-business-baseline/roundtrip-manifest.json`
  - DOCX/PPTX all expose `native_images=True`
  - PPTX all expose `native_editable_charts=True`
  - PDFs all expose `has_vector_layout=True`
  - LibreOffice conversion remains `skip_no_libreoffice`
- P2.5 office sample validation generated `/tmp/af-p25-office` and passed
  non-GUI DOCX/PPTX/PDF structure validation; LibreOffice conversion was
  recorded as `skip_no_libreoffice`; PDF QuickLook thumbnail validation passed.
- P2.5 explicit GUI launch gate passed:
  `/tmp/af-p25-office/gui-open-manifest.json` records Word, PowerPoint, and
  Preview `status=launched` for the generated DOCX/PPTX/PDF samples. This only
  confirms app launch; final visual correctness still needs human inspection.
- Historical low-quality audit remains `20/66` flagged and wrote
  `/tmp/af-quality-audit-v180-p23.json` plus
  `/tmp/af-quality-audit-v180-p23.md`
- Generated temporary office validation artifacts under `/tmp/af-p23-office`;
  `scripts/validate_office_roundtrip.py` passed DOCX/PDF/PPTX structure checks,
  and PDF QuickLook thumbnail rendering passed.
- Local office capability detection: no LibreOffice CLI; macOS QuickLook,
  Microsoft Word.app, and Microsoft PowerPoint.app are available.
- `npm run security:scan` passed
- `npm run security:scan:history` passed
- `git diff --check` passed
- `npm run repo:screenshots` passed
- Screenshot manifest contains 30 accepted screenshots:
  - 15 light
  - 15 dark
  - current release version `1.8.0`
  - refreshed after P2.2 formal-delivery UI changes

Locked evaluation baseline from the prior `1.7.2` line:

- Evaluation governance/dataset targeted tests: 7 passed
- `npm run research:evaluate` passed for the locked 100-case manifest
- `npm run research:evaluate:parity` passed at `100/100`

Current repository counts for orientation:

- 704 tracked files
- 68 backend `test_*.py` files
- 5 frontend test files
- 24 Alembic migration files

Current offline parity artifact:

- Dataset version: `1.2.0`
- Cases: `100`
- Passed: `100`
- Failed: `0`
- Parity rate: `1.0`
- Production gate passed: yes
- Network/model cost: none
- Artifact:
  `.tmp/research-workflow-parity.json`

Important interpretation:

- This proves orchestration contract equivalence.
- It does not prove live source freshness, retrieval quality, provider latency,
  provider structured-output reliability, or final answer quality.

## 10. Evaluation Dataset and Review Context

Tracked dataset:

```text
backend/evaluation/research_golden_v1.json
```

Current metadata:

- Dataset ID: `anti-fomo-research-golden-v1`
- Dataset version: `1.2.0`
- Status: `locked`
- Cases: `100`
- Suites: `10`, 10 cases each
- Digest:
  `f52835846045726158277abf5212dda8370d3b23d4b17229df161b827e514df5`

Tracked scope resolution:

```text
backend/evaluation/research_scope_feedback_resolution_v1_2.json
```

Local review state:

- `.tmp/research-evaluation-independent-review.json`
  - current dataset version `1.2.0`
  - current digest
    `f52835846045726158277abf5212dda8370d3b23d4b17229df161b827e514df5`
  - status `pending`
  - 100/100 decisions still `pending`
  - now includes locked `regions` and `entities` for meaningful review of the
    1.7.2 scope corrections
  - no reviewer role, attestation, date, or digest
  - must not be treated as a completed review
- `.tmp/research-evaluation-independent-review-100-cases.csv`
  - stale dataset version `1.1.0`
  - blank review fields
- `.tmp/research-live-evaluation-plan-v1.2.json`
  - 100 cases
  - 20 batches of 5
  - target full-suite ceiling `$81.50`
  - no approved budget

External/local review files in Downloads:

```text
/Users/chenhaorui/Downloads/研究评测集-100条-独立专家复核表-中文版.csv
/Users/chenhaorui/Downloads/研究评测集-专家意见处理结果-2026-06-15.md
/Users/chenhaorui/Downloads/研究评测集-专家意见处理结果及二次确认表-79条.csv
```

Second-confirmation status:

- 79 rows: 78 revised cases + `transport-003`
- `二次确认结论`: blank for all 79
- `二次确认意见`: blank for all 79
- Therefore the post-change independent approval gate is not complete.

Formal independent review requirements:

1. Review all 100 current `1.2.0` cases.
2. Confirm the current locked region, research subject, behavior, answer terms,
   and expected source domains.
3. Write a substantive note for every case.
4. Use a reviewer different from the original maintainer/Codex-assisted locker.
5. Supply reviewer name, role, date, and attestation.
6. Finalize and pass review-content digest validation.

Commands:

```bash
npm run research:evaluate:review:export

npm run research:evaluate:review:finalize -- \
  --review .tmp/research-evaluation-independent-review.json \
  --reviewer-name "<independent reviewer>" \
  --reviewer-role "<domain role>" \
  --attestation "I independently reviewed all cases against the locked criteria."

npm run research:evaluate:review:validate -- \
  --review .tmp/research-evaluation-independent-review.json
```

The review artifact may contain personal information. Keep it in ignored local
storage unless publication is deliberate and approved.

## 11. Authenticity and Tender Verification Context

Additional local verification was completed on 2026-06-15. These results are
not the same thing as the evaluation dataset lock.

Files:

```text
/Users/chenhaorui/Downloads/研究评测集-100条-真实性与招投标核验明细-2026-06-15.csv
/Users/chenhaorui/Downloads/研究评测集-真实性与招投标核验说明-2026-06-15.md
```

Classification:

- A1 official/first-party direct match: `4`
- A2 highly matching procurement lead, still needs official detail: `13`
- B real related project, not a unique match: `22`
- C no unique matching project found: `45`
- D non-project or safety/refusal case: `16`

Claim rules:

- Only A1 may be described as officially/first-party confirmed.
- A2 is a highly matching lead, not final proof.
- B may only be described as a related real project.
- C means public evidence was insufficient as of 2026-06-15; it does not prove
  non-existence.
- D must not be converted into fabricated project, budget, supplier, contact,
  or internal-data claims.

## 12. Current Unfinished Work

### P0: Complete post-change independent review

The `1.2.0` dataset has been corrected and locked, but the replacements have not
been independently approved.

### P0: Continue the inserted `1.8.0` professional-report quality line

`1.8.0` is now the next product version and takes precedence over later generic
export enhancements.

Completed locally:

- Added deterministic content-hygiene review for webpage navigation, footer,
  login, source-dump, and template contamination.
- Added claim-to-evidence traceability review for numeric, budget, duration,
  benefit, and recommendation claims.
- Added semantic score caps so contaminated material fails and structure-only
  material without concrete evidence anchors cannot pass.
- Added targeted regression tests for the previous false-high-score failure.
- Completed P0.2:
  - stable `clm_*`, `ev_*`, and `issue_*` identifiers
  - support/conflict/background/needs-validation evidence relationships
  - overall and high-confidence evidence coverage
  - target customer / owner / buyer / winning-vendor entity-role checks
  - normalized CNY, duration, percentage, and calendar-year handling
  - non-scenario numeric conflict detection
  - solution Markdown, formal-document appendix, API, and frontend visibility
- Completed P0.3 first implementation:
  - stable `sch_*` semantic-challenger issue IDs
  - scope-drift checks against locked customer/scenario/vertical scope
  - cross-section target-customer/owner/buyer entity conflict detection
  - cross-section numeric conflict detection across budget, amount, duration,
    percentage, and concurrency facts
  - unsupported high-confidence claim checks on top of the evidence ledger
  - source-contamination and template-placeholder checks
  - versioned de-identified real-project-style golden samples:
    `gov-ai-service-center`, `tourism-aigc-guide`,
    `smart-manufacturing-quality-platform`
  - solution-pack API, formal-document appendix, Markdown export, frontend
    delivery-card, and TypeScript contract visibility
- Completed P1.1 first implementation:
  - added structured `compiled_documents` DTOs with document kind, framework,
    audience, purpose, evidence policy, sections, assumptions, validation
    actions, quality gates, and Markdown
  - added dedicated compilers:
    `solution_design_compiler_v1`, `consulting_report_compiler_v1`,
    `project_proposal_compiler_v1`, `feasibility_study_compiler_v1`
  - solution design covers business goals, use cases, capability architecture,
    data/model/interface integration, NFR, security, implementation, acceptance,
    evidence, and risk
  - consulting report covers SCQA, problem tree, hypotheses, insights,
    counterarguments, options, trade-offs, recommendation, and 30/60/90-day
    action plan
  - project proposal and feasibility study now adapt from their own compiler
    outputs instead of a shared generic section builder
  - formal Word/PDF exports preserve manual supplemental context/evidence in
    “人工输入与交叉验证说明”
  - solution-pack Markdown, frontend delivery card, and TypeScript contracts
    expose the four compiler outputs
- Completed P1.2 first implementation:
  - added structured `quantitative_decision_model` DTOs and
    `delivery_quantitative_decision_model_v1`
  - added weighted alternatives for status quo, phased pilot, and full build
  - added tender scoring response matrix with section, evidence, owner, risk,
    and validation-action mapping
  - added conservative/base/optimistic finance scenarios with CAPEX, OPEX,
    3-year TCO, benefits, NPV, IRR, ROI, and payback period when amount evidence
    exists
  - missing finance inputs remain explicit assumptions and do not generate fake
    numbers
  - added sensitivity variables for CAPEX, OPEX ratio, benefit ratio, and
    discount rate
  - solution-pack Markdown, formal Word/PDF appendices, frontend delivery card,
    and TypeScript contracts expose the quantitative model
- Completed P1.3 first real-business golden sample gate:
  - added `backend/evaluation/real_business_delivery_golden_v1.json`
    (`anti-fomo-real-business-delivery-golden-v1`) with 3 source-backed 2026
    topics:
    `shanghai-medical-ai-2026`,
    `shanghai-culture-tourism-ai-2026`,
    `yangtze-delta-gov-ai-2026`
  - registered the same IDs in `backend/evaluation/delivery_golden_samples_v1.json`
    for semantic-challenger alignment
  - deterministic loader/report construction lives in
    `backend/app/services/research/real_business_golden_samples.py`
  - policy-only and pilot-notice sources no longer create fake tender projects;
    delivery copy falls back to policy/pilot opportunity preparation when no
    true tender evidence exists
  - missing public project amounts keep P1.2 financial scenarios as
    `assumption_required` instead of generating pseudo CAPEX/NPV/IRR/ROI
  - targeted P1.3 validation passed `14/14`; samples remain
    `draft_for_blind_review` until manual evidence anchoring and expert review

Next sequence:

1. Continue P2 formal delivery engineering after P2.7: if automated headless
   Office→PDF conversion is required, fix Homebrew/GitHub network and install
   LibreOffice or set `ANTI_FOMO_LIBREOFFICE_CLI` to an existing `soffice`
   binary. P2.7 already adds native PDF image objects and launched representative
   Word/PowerPoint/Preview windows; the remaining subjective step is human visual
   inspection of those windows.
2. Run the next historical low-quality audit and quantify whether P0.3/P1.3
   reduce the 20/66 baseline once enough newly generated reports exist.
3. Collect expert blind-review ratings for the three real-business golden themes
   and the four document types; do not treat `draft_for_blind_review` samples as
   client-approved deliverables.
4. Ask a finance/business owner to validate CAPEX, tax, discount-rate, payment,
   and benefit-attribution assumptions before treating P1.2 output as client-ready.
5. Keep paid live-model evaluation disabled unless explicitly approved.

Detailed plan:

```text
docs/professional-report-quality-v1.8.0.md
```

Recommended sequence:

1. Complete the 79-row second-confirmation sheet.
2. Complete all 100 entries in the regenerated current `1.2.0` formal review
   artifact.
3. Finalize with independent reviewer metadata and attestation.
4. Validate the digest.
5. Keep private reviewer artifacts local unless approved for publication.

### P0: Do not run paid full-suite evaluation yet

Full target ceiling is `$81.50`, 20 batches of five.

Before any live run:

- obtain explicit user-approved budget
- configure provider prices; do not guess them
- validate the current independent review artifact
- start with one case or one five-case batch
- preserve live artifacts separately from offline parity

Example bounded command after approval:

```bash
npm run research:evaluate -- \
  --execute \
  --case-id gov-cloud-001 \
  --workflow-engine langgraph \
  --allow-live-provider \
  --review .tmp/research-evaluation-independent-review.json \
  --budget-usd 0.80
```

### P1: Review the current uncommitted governance slice

Completed locally on 2026-06-18:

- Chinese README now covers `1.7.0` through `1.7.2` and reports the current
  release truth.
- Changelog now contains `1.7.0`, `1.7.1`, and `1.7.2` sections.
- Screenshot manifest is aligned to `1.7.2` while recording that the unchanged
  UI assets come from the accepted `1.6.0` baseline.
- Screenshot coverage documentation and the stale roadmap statement are fixed.
- Independent-review artifacts now include locked `regions` and `entities`;
  validation blocks any scope-context alteration.
- The `.tmp` formal review template was regenerated for dataset `1.2.0`.

Current state:

- 10 tracked files are modified.
- No commit, tag, GitHub push, or ModelScope push has been performed.
- Review the diff before deciding whether to commit this slice.

Backend startup fix completed locally on 2026-06-19:

- `demo:start` previously preferred an incomplete `.venv312`, causing research
  jobs to fail with `No module named 'langgraph'`.
- Backend startup now selects the first Python environment that can import
  `fastapi`, `sqlalchemy`, `uvicorn`, and `langgraph`, with the setup-managed
  `.venv311` checked first.
- Both `demo:start` and `demo:backend` use the shared selector.
- The running backend was restarted on `.venv311`; workflow import and the four
  LangGraph workflow tests passed.

Theme, WeChat, and report-quality slice completed locally on 2026-06-19:

- Semantic theme compatibility now covers all 15 primary surfaces and nested
  state cards. The release screenshot manifest contains 30 accepted images,
  split 15 light / 15 dark.
- The active research progress card and shared progress ring use semantic
  surface, border, text, and accent variables instead of fixed white styles.
- WeChat Favorites import now commits `CollectorImportBatch` before returning.
  A live deduplicated import produced a durable batch and subsequent GET/list
  calls returned it successfully.
- Frontend batch restoration clears stale IDs and falls back to item review
  instead of silently polling a missing batch forever.
- The collector has an optional `wechat-cli favorites --type article` adapter
  with incremental seen-link state and status fields. The local machine does
  not currently have `wechat-cli`; latest state is `unavailable`. Do not install
  or perform memory/signature modifications without explicit user approval.
- WeChat browser extraction waits for `#js_content`, keeps canonical URLs, and
  rejects parameter-error, verification, and expired-link shells. The supplied
  failing URL is now classified `access_limited=true` instead of accepted as a
  75-character article.
- Research prompts now explicitly perform perspective decomposition,
  multi-source summaries, contradiction/negative-evidence checks, outline-first
  drafting, and adversarial self-review.
- Feasibility and proposal delivery axes now cover alternatives, architecture,
  security, implementation/procurement, operations, investment, impacts, risks,
  evidence matrices, and assumption ledgers, aligned to the NDRC 2023 outline.
- The legacy OpenAI adapter's missing `_QuotaExhaustedError` and Chinese
  `额度已用尽` detection were fixed. Current dry-run reaches provider `openai`
  with model `gpt-5.5`; it no longer drops to deterministic mock.
- Verification completed:
  - frontend lint, 16 frontend tests, and Next production build passed
  - final full backend suite passed `310/310`
  - quota adapter tests pass `8/8`
  - targeted WeChat/delivery tests passed `21/21`
  - screenshot capture passed with 30 light/dark assets
  - `git diff --check` passed

`1.8.0` professional-report quality line started locally on 2026-06-19:

- Added deterministic delivery content-hygiene scoring for webpage navigation,
  footer, login, source-dump, and template contamination.
- Added claim-to-evidence traceability scoring for numeric, budget, duration,
  benefit, and recommendation claims.
- Added semantic hard caps:
  - contaminated delivery content remains `fail`
  - structure-only material without concrete URL/document/project/source/chunk
    anchors cannot enter `pass`
- Added three regression cases covering the prior false-high-score behavior,
  polluted delivery content, and fully traceable strong claims.
- Preserved the existing solution-delivery and formal-document API contracts.
- Verification completed:
  - targeted delivery/evaluation tests passed `14/14`
  - `npm run check` passed
  - frontend tests passed `16/16`
  - backend tests passed `325/325`
  - production build passed
  - historical audit baseline remained `20/66` flagged, so the 30.3% baseline
    is preserved rather than redefined
  - `git diff --check` passed
- P0.2 verification additionally confirmed:
  - claim/evidence IDs stay stable when row and source order changes
  - equivalent `520 万元` and `0.052 亿元` values do not conflict
  - conflicting target-customer roles and conflicting budget values create
    stable high-severity issues
  - formal feasibility/proposal documents include the ledger appendix
- P0.3 targeted verification completed:
  - `backend/tests/test_delivery_semantic_challenger.py`
  - `backend/tests/test_delivery_golden_samples.py`
  - plus related ledger, semantic-quality, solution-intelligence, and
    delivery-material tests
  - targeted command passed `19/19`
  - full `npm run check` passed after P0.3: ESLint, frontend `16/16`,
    Next production build, backend `325/325`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p03.json` plus
    `/tmp/af-quality-audit-v180-p03.md`
  - `git diff --check` passed
- P1.1 targeted verification completed:
  - `backend/tests/test_delivery_document_compilers.py`
  - `backend/tests/test_delivery_solution_materials.py`
  - `backend/tests/test_research_solution_intelligence_service.py`
  - `backend/tests/test_daily_brief_and_extended_tasks.py`
  - `backend/tests/test_research_solution_delivery_exports.py`
  - targeted command passed `15/15`
  - full `npm run check` passed after P1.1: ESLint, frontend `16/16`,
    Next production build, backend `328/328`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p11.json` plus
    `/tmp/af-quality-audit-v180-p11.md`
  - `git diff --check` passed
- P1.2 targeted verification completed:
  - `backend/tests/test_delivery_quantitative_models.py`
  - `backend/tests/test_delivery_document_compilers.py`
  - `backend/tests/test_delivery_solution_materials.py`
  - `backend/tests/test_research_solution_intelligence_service.py`
  - `backend/tests/test_daily_brief_and_extended_tasks.py`
  - `backend/tests/test_research_solution_delivery_exports.py`
  - targeted command passed `19/19`
  - full `npm run check` passed after P1.2: ESLint, frontend `16/16`,
    Next production build, backend `332/332`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p12.json` plus
    `/tmp/af-quality-audit-v180-p12.md`
  - `git diff --check` passed
  - current Git-visible modified/untracked count is `95`; many entries are
    accumulated from prior slices and should not be committed/tagged/pushed
    without explicit user instruction
- P1.3 real-business golden sample validation completed:
  - added `backend/tests/test_real_business_delivery_golden_samples.py`
  - targeted command passed `14/14`:
    `backend/tests/test_real_business_delivery_golden_samples.py`,
    `backend/tests/test_delivery_golden_samples.py`,
    `backend/tests/test_delivery_semantic_challenger.py`,
    `backend/tests/test_delivery_solution_materials.py`,
    `backend/tests/test_research_solution_intelligence_service.py`
  - full `npm run check` passed after P1.3: ESLint, frontend `16/16`,
    Next production build, backend `335/335`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-real-golden.json` plus
    `/tmp/af-quality-audit-v180-real-golden.md`
  - `git diff --check` passed
  - current Git-visible modified/untracked count is `100`; many entries are
    accumulated from prior slices and should not be committed/tagged/pushed
    without explicit user instruction
- P2.1 formal delivery rendering slice completed locally:
  - added controlled rendering for feasibility-study and project-proposal
    formal exports without changing the existing task API
  - Word-compatible `.doc` HTML now includes A4 page CSS, metadata tables,
    table of contents, controlled section tables, Word header/footer hooks,
    delivery layout-control checklist, and PDF/Word round-trip checklist
  - formal sections are renumbered through `_number_formal_document_sections`:
    main sections use Chinese numerals; manual inputs, quality gates,
    claim/evidence appendices, semantic-challenger records, and quantitative
    model sections use Appendix A/B/C numbering
  - legacy aliases such as `附：量化决策模型摘要` and `data-plain="目标客户：..."`
    remain in the exported HTML so existing text search and downstream checks
    continue to work
  - simple PDF renderer now accepts optional per-page header/footer, and formal
    PDF previews include `Anti-FOMO 正式交付` plus `P2 controlled export`
  - added `backend/tests/test_formal_document_rendering.py`
  - targeted command passed `14/14`:
    `backend/tests/test_formal_document_rendering.py`,
    `backend/tests/test_daily_brief_and_extended_tasks.py`,
    `backend/tests/test_delivery_quantitative_models.py`,
    `backend/tests/test_research_solution_delivery_exports.py`
  - full `npm run check` passed after P2.1: ESLint, frontend `16/16`,
    Next production build, backend `337/337`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p21.json` plus
    `/tmp/af-quality-audit-v180-p21.md`
  - `git diff --check` passed
  - current Git-visible modified/untracked count is `102`; many entries are
    accumulated from prior slices and should not be committed/tagged/pushed
    without explicit user instruction
- P2.2 native artifact / proofreading / visual-regression slice completed locally:
  - added `backend/app/services/work_tasks/openxml.py`, a dependency-free
    OpenXML generator for native DOCX and editable PPTX zip/XML artifacts
  - added `backend/app/services/work_tasks/chinese_proofreading.py` for
    deterministic Chinese proofreading findings: half-width punctuation in CJK
    context, repeated punctuation, long digits without units, CJK spacing,
    unclosed brackets, absolute promises, and unresolved `待核验` markers
  - feasibility-study and project-proposal Word tasks now return `.docx`,
    Office OpenXML MIME, and `content_base64`; `content` remains an HTML
    preview for current frontend compatibility
  - feasibility-study and project-proposal PDF tasks now share the same formal
    render payload and expose `formal_rendering` diagnostics with round-trip
    checklist, proofreading findings, and visual-regression fingerprint
  - solution delivery can export `export_research_solution_delivery_pptx` with
    editable text boxes; API task schemas, WorkBuddy task typing, frontend task
    typing, and the Inbox export button were updated
  - formal-rendering diagnostics now include required markers for future
    screenshot/file round-trip comparisons
  - `npm run repo:screenshots` passed and refreshed the 30 light/dark screenshot
    baselines and manifest
  - targeted command passed `18/18`:
    `backend/tests/test_formal_document_rendering.py`,
    `backend/tests/test_daily_brief_and_extended_tasks.py`,
    `backend/tests/test_research_solution_delivery_exports.py`,
    `backend/tests/test_delivery_quantitative_models.py`
  - full `npm run check` passed after P2.2: ESLint, frontend `16/16`,
    Next production build, backend `341/341`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p22.json` plus
    `/tmp/af-quality-audit-v180-p22.md`
  - `git diff --check` passed
  - current Git-visible modified/untracked count is `109`; many entries are
    accumulated from prior slices and should not be committed/tagged/pushed
    without explicit user instruction
  - limitation: DOCX/PPTX are valid minimal OpenXML artifacts and editable text
    outputs, but not yet a full Word/PowerPoint template system; PDF remains a
    controlled in-repo preview, not a complex external layout engine
- P2.3 real-office validation / professional-template slice completed locally:
  - upgraded `backend/app/services/work_tasks/openxml.py`:
    - DOCX now includes P2.3 professional template markers, executive dashboard,
      `word/settings.xml`, updateFields, Word TOC field, chart/image layout
      placeholders, captions, stronger styles, and VML placeholder boxes
    - PPTX now includes `ppt/theme/theme1.xml`, professional color palette,
      key-takeaway card, evidence/assumption card, editable chart placeholder,
      image placeholder, and editable text boxes
  - added `backend/app/services/work_tasks/office_roundtrip.py`:
    - detects LibreOffice CLI, macOS QuickLook, Microsoft Word.app, and
      Microsoft PowerPoint.app without launching GUI apps
    - validates DOCX/PPTX zip structure, required OpenXML parts,
      XML well-formedness, and required text markers
    - validates PDF header/EOF/page count
  - added `scripts/validate_office_roundtrip.py` and npm script
    `office:roundtrip`; default is non-GUI validation, `--quicklook` renders
    thumbnails when available, and `--open-gui` must be explicit before opening
    Word/PowerPoint/Preview
  - current local capability result: no LibreOffice CLI; `/usr/bin/qlmanage`,
    `/Applications/Microsoft Word.app`, and
    `/Applications/Microsoft PowerPoint.app` are present
  - generated sample artifacts under `/tmp/af-p23-office` and validated:
    - DOCX/PDF/PPTX structure checks passed
    - PDF QuickLook thumbnail rendering passed
    - PPTX QuickLook thumbnail hung past 60 seconds; process was killed and
      script now has a per-file timeout, so PPTX GUI validation remains an
      explicit manual/`--open-gui` gate
  - targeted command passed `20/20`:
    `backend/tests/test_formal_document_rendering.py`,
    `backend/tests/test_daily_brief_and_extended_tasks.py`,
    `backend/tests/test_research_solution_delivery_exports.py`,
    `backend/tests/test_delivery_quantitative_models.py`
  - full `npm run check` passed after P2.3: ESLint, frontend `16/16`,
    Next production build, backend `343/343`
  - historical audit command remained `20/66` flagged and wrote
    `/tmp/af-quality-audit-v180-p23.json` plus
    `/tmp/af-quality-audit-v180-p23.md`
  - `git diff --check` and `npm run security:scan` passed
  - current Git-visible modified/untracked count is `112`; many entries are
    accumulated from prior slices and should not be committed/tagged/pushed
    without explicit user instruction
  - limitation: this is still a generated professional template scaffold, not
    a full customer brand template system with real charts/images and
    LibreOffice/headless conversion in CI
- P2.4 brand/media/renderer-strategy slice completed locally:
  - `delivery_supplement` now accepts structured `brand_template`,
    `chart_assets`, `image_assets`, and `renderer_strategy` without changing the
    existing task API.
  - Formal render payload now carries normalized customer brand templates,
    real-data chart assets, replaceable image assets, and a headless conversion
    strategy. If no structured assets are supplied, deterministic defaults are
    derived from budget signals, source counts, evidence density, source quality,
    customer, scenario, and implementation window.
  - DOCX OpenXML exports now write:
    - `Anti-FOMO P2.3 专业交付模板 / P2.4 客户品牌与可替换资产模板`
      marker
    - customer brand row, brand colors, logo text and confidentiality label
    - `P2.4 可替换资产清单`
    - `真实数据图表` rows with source/unit/period/replacement slot/data summary
    - `可替换图片资源` rows with source/authorization/replacement slot
    - VML placeholder boxes using the brand secondary/accent colors
  - PPTX OpenXML exports now write a customer-named theme, brand color accents,
    editable brand label, chart/image cards populated from the asset list, and
    still preserve the old `Anti-FOMO P2.3 editable PPTX template` compatibility
    marker.
  - PDF/HTML/plaintext previews and diagnostics now include P2.4 required
    markers, brand metadata, replaceable asset counts/titles, and
    `headless_conversion_strategy`.
  - Headless conversion decision: do not auto-install LibreOffice or launch GUI
    apps. Default remains controlled in-repo preview plus OpenXML/PDF structure
    validation; LibreOffice headless or real Word/PowerPoint opening should be
    an explicit/manual external-send gate.
  - targeted commands passed `25/25`:
    `backend/tests/test_formal_document_rendering.py`,
    `backend/tests/test_research_solution_delivery_exports.py`,
    `backend/tests/test_daily_brief_and_extended_tasks.py`,
    `backend/tests/test_delivery_quantitative_models.py`,
    `backend/tests/test_delivery_document_compilers.py`
  - full `npm run check` passed after P2.4: ESLint, frontend `16/16`,
    Next production build, backend `345/345`
  - current limitation: chart assets are represented as editable text/card data
    and VML/PPTX placeholder shapes, not yet full native Office chart objects;
    PDF remains a controlled text-layout preview, not a production desktop
    publishing engine.
- P2.5 Office-open validation / complex-template / native-chart slice completed
  locally:
  - `office_roundtrip.py` now exposes:
    - `headless_conversion` capability with `libreoffice_headless` command when
      LibreOffice CLI exists, otherwise `skip_no_libreoffice`
    - `real_open_validation_gate` for Word, PowerPoint, and Preview, with policy
      `never_launch_gui_in_tests`
    - `complex_template_parts`, `native_chart_parts`, `embedded_workbooks`, and
      `native_editable_charts` in OpenXML validation results
    - PDF `professional_layout_checks`
  - `scripts/validate_office_roundtrip.py` now supports:
    - `--libreoffice-convert` for explicit LibreOffice headless PDF conversion
    - `--manifest-out` for writing JSON validation manifests
    - existing `--open-gui` remains explicit-only for Word/PowerPoint/Preview
  - DOCX OpenXML exports now include:
    - `word/theme/theme1.xml`
    - `word/numbering.xml`
    - relationships for theme and numbering
    - custom styles `AFBrandBand`, `AFChecklist`, `AFSmallNote`
    - visible `P2.5 复杂样式模板与真实打开验证门禁` section
  - PPTX OpenXML exports now include a native editable chart object:
    - `ppt/charts/chart1.xml`
    - `ppt/charts/_rels/chart1.xml.rels`
    - `ppt/embeddings/chart-data.xlsx`
    - slide relationship `rIdChart1`
    - slide graphic frame named `P2.5 Native Editable Chart`
  - diagnostics now expose `complex_style_template`,
    `office_validation_gate`, `native_editable_charts`, `native_chart_parts`,
    and `embedded_workbooks`; visual regression required markers now include
    P2.5 chart/template expectations.
  - targeted commands passed `25/25`:
    `backend/tests/test_formal_document_rendering.py`,
    `backend/tests/test_research_solution_delivery_exports.py`,
    `backend/tests/test_daily_brief_and_extended_tasks.py`,
    `backend/tests/test_delivery_quantitative_models.py`,
    `backend/tests/test_delivery_document_compilers.py`
  - generated sample artifacts under `/tmp/af-p25-office`; `npm run
    office:roundtrip -- ... --libreoffice-convert --manifest-out
    /tmp/af-p25-office/roundtrip-manifest.json` passed. LibreOffice conversion
    was skipped because no LibreOffice CLI is installed locally.
  - PDF QuickLook visual smoke gate passed and wrote
    `/tmp/af-p25-office/pdf-quicklook-manifest.json` plus thumbnails under
    `/tmp/af-p25-office/quicklook`; the manifest now includes thumbnail
    `sha256` fingerprints for future visual regression baselines.
  - explicit GUI open gate passed:
    `npm run office:roundtrip -- /tmp/af-p25-office/*.docx
    /tmp/af-p25-office/*.pptx /tmp/af-p25-office/*.pdf --open-gui
    --manifest-out /tmp/af-p25-office/gui-open-manifest.json` launched
    Microsoft Word, Microsoft PowerPoint, and Preview successfully.
  - full `npm run check` passed after P2.5: ESLint, frontend `16/16`,
    Next production build, backend `345/345`
  - current limitation: GUI launch succeeded, but automated checks cannot judge
    human visual polish inside the apps. PDF is still controlled text layout,
    not a full desktop publishing engine with embedded raster/vector image
    placement.
- P2.6 production PDF/image-layout and historical artifact visual baseline slice
  completed locally:
  - DOCX OpenXML exports now embed deterministic native PNG media:
    `word/media/image1.png`, `word/_rels/document.xml.rels` image relationship
    `rIdImage1`, and visible DrawingML marker `原生图片嵌入`.
  - PPTX OpenXML exports now embed deterministic native PNG media:
    `ppt/media/image1.png`, slide relationship `rIdImage1`, and visible picture
    shape marker `原生图片嵌入`.
  - `office_roundtrip.py` now reports `native_image_parts` and `native_images`
    for DOCX/PPTX; PDF validation reports `has_vector_layout` and
    `vector_brand_frame_present`.
  - Controlled PDF preview now uses layout profile
    `p2.6-brand-media-grid`, injecting vector header band, page frame, side bars
    and guide rules; diagnostics expose
    `professional_pdf_layout_version=p2.6-vector-brand-media-grid-preview`.
  - New script `scripts/generate_formal_artifact_visual_baseline.py` and npm
    command `npm run office:visual-baseline` generate DOCX/PPTX/PDF artifacts
    for all real-business golden samples, write a JSON manifest, validate each
    artifact, and optionally generate PDF QuickLook thumbnail hashes.
  - Baseline manifests include both raw `sha256` and stable
    `normalized_sha256`; normalized hashes ignore volatile OpenXML zip metadata
    and core created/modified timestamps.
  - QuickLook default scope is PDF-only because this macOS setup can timeout on
    PPTX thumbnails; `--quicklook-all` remains available for manual broader
    smoke checks.
  - generated all real-business baseline artifacts under
    `/tmp/af-p26-real-business-baseline`; summary: `sample_count=3`,
    `artifact_count=9`, `failed_validation_count=0`,
    `failed_quicklook_count=0`.
  - independent `npm run office:roundtrip -- ... --libreoffice-convert` over
    the same 9 artifacts passed; LibreOffice conversion was skipped because no
    local LibreOffice CLI is installed.
  - targeted affected validation passed `28/28`.
  - current limitation: PDF remains a controlled in-repo preview with vector
    professional framing, not a full desktop publishing/rendering stack. Final
    customer-facing visual polish still requires human Word/PowerPoint/Preview
    inspection and/or LibreOffice/headless renderer validation.
- P2.7 PDF native image / LibreOffice configuration / GUI visual-gate slice
  completed locally:
  - `_build_simple_pdf` now writes a native PDF Image XObject `/Im1` with
    `/Subtype /Image`, `/ColorSpace /DeviceRGB`, `/Filter /FlateDecode`, and
    draws it into the `p2.6-brand-media-grid` media slot.
  - `validate_pdf_bytes` now reports `has_native_image` and
    `native_pdf_image_present`.
  - formal PDF diagnostics now expose
    `professional_pdf_layout_version=p2.7-vector-brand-media-image-preview` and
    `native_pdf_image_embedding=p2.7-pdf-image-xobject`.
  - LibreOffice detection now checks `ANTI_FOMO_LIBREOFFICE_CLI`,
    `LIBREOFFICE_CLI`, `SOFFICE_PATH`, the macOS app bundle path and common
    Homebrew symlinks before falling back to PATH.
  - Homebrew LibreOffice installation was attempted but blocked by network/API
    failures outside the repo; no LibreOffice CLI is available at handoff time.
  - P2.7 real-business baseline lives under
    `/tmp/af-p27-real-business-baseline`; 9 artifacts passed validation and PDF
    QuickLook, representative GUI open manifest shows Word/PowerPoint/Preview
    launched successfully.

### P2: Later product improvements

From the current roadmap:

- ADR table export
- Integration/dependency workshop checklist
- Stakeholder brief
- Customer technical workshop agenda
- Plugin/extensibility boundaries only after core module stability

### P2: Refactor only on real ownership boundaries

Monitored hotspots include:

- `scripts/wechat_pc_full_auto_agent.py`
- `backend/app/services/research_service.py`
- `backend/app/services/wechat_pc_agent_daemon.py`
- `backend/app/schemas/research.py`
- `backend/app/services/research_retrieval_index_service.py`
- `backend/app/services/research_workspace_store.py`
- `backend/app/api/research.py`
- `src/components/inbox/inbox-form.tsx`
- `src/components/session/session-summary-panel.tsx`
- `src/components/research/research-markdown-archive-viewer.tsx`

Do not mechanically split them. Extract only with:

- a stable named responsibility
- an independently testable contract
- reduced dependency direction or compatibility risk
- regression tests before movement

## 13. Security and Local-Only Files

Never print, summarize, or commit values from:

```text
backend/.env
miniapp/project.private.config.json
*.db
*.db.before-*
.tmp/
.storage/
```

Important local files:

- `backend/anti_fomo_demo.db.before-entity-quality-20260502-021530`
  - SQLite backup
  - about 39 MB
  - created/modified 2026-05-02
  - preserve, do not commit
- `backend/.env`
  - contains runtime configuration/secrets
- `miniapp/project.private.config.json`
  - private WeChat DevTools configuration

The repository already ignores these patterns.

Secret-release gates:

```bash
npm run security:scan
npm run security:scan:history
```

The PostCSS override is intentional:

```json
{
  "overrides": {
    "postcss": "8.5.15"
  }
}
```

Do not remove it until a stable Next.js version uses a safe PostCSS version and
passes install, audit, build, and regression checks. Do not accept the audit
tool's incompatible Next.js 9 downgrade.

## 14. Environment and Run Commands

Setup:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:setup
```

Start/stop:

```bash
npm run demo:start
npm run demo:stop
```

Default URLs:

- Frontend: `http://localhost:3010`
- Backend: `http://localhost:8000`

Core checks:

```bash
npm run check
npm run demo:smoke
npm run repo:screenshots
npm run security:scan
npm run security:scan:history
git diff --check
```

Evaluation checks:

```bash
npm run research:evaluate
npm run research:evaluate:parity
npm run research:evaluate:plan-live
```

Collector/agent checks:

```bash
npm run collector:status
npm run wechat-agent:status
npm run workbuddy:doctor
```

## 15. Key Documentation

Read in this order for continued work:

1. `memory.md`
2. `docs/current-version-and-refactor-roadmap-2026-05-20.md`
3. `docs/module-ownership-map-2026-05-21.md`
4. `docs/release-history-and-feature-map.md`
5. `docs/research-evaluation-scope-feedback-v1.7.2.md`
6. `docs/research-evaluation-governance-v1.7.1.md`
7. `docs/langgraph-production-v1.7.0.md`
8. `docs/backend-hotspot-assessment-2026-06-14.md`
9. `docs/release-hardening-v1.6.0.md`
10. `docs/next-chat-handoff-2026-05-18.md`

Older documents are useful as implementation history, but some contain stale
version/status wording. Prefer current code, current Git state, and the latest
version-specific documents.

## 16. Working Protocol for the Next Agent

Before editing:

1. Read this file.
2. Run `git status --short --branch`.
3. Confirm `package.json` version and HEAD.
4. Read the owner module and its existing tests.
5. Preserve unrelated local changes and ignored artifacts.

During implementation:

- Keep changes small and ownership-aligned.
- Preserve API compatibility unless versioning is deliberate.
- Add tests proportional to risk.
- Keep deterministic rollback healthy for workflow changes.
- Run full offline parity for workflow orchestration changes.
- Use semantic theme tokens for new UI.
- Avoid live provider calls unless explicitly approved.

Before handing off:

1. Run targeted tests.
2. Run `npm run check` for material changes.
3. Run parity for workflow changes.
4. Run screenshots for release-critical UI changes.
5. Run both secret scans before release/history publication.
6. Update release docs and this memory if project truth changed.
7. Report exact checks, known gaps, and whether anything was committed/pushed.

## 17. 2026-06-21 Design Bug Sweep Handoff

Current user request was a visual/design anomaly sweep based on the Research
Center screenshot, not the unrelated downloaded Markdown reference.

Completed fixes:

- Fixed the Research Center header action bug where the `公开源` status control
  reused the icon-only `af-glass-orb-btn` class and collapsed into a tiny
  circular icon. It now uses an `af-pill` text-safe status pill and semantic
  theme tokens.
- Hardened the top navigation orb controls:
  - `af-glass-orb-btn` / `af-glass-orb-badge` no longer shrink in the nav flex
    row.
  - `AF` badge has a minimum width and explicit accessible label.
  - mobile nav uses `justify-start md:justify-end` plus active-item
    `scrollIntoView`, so the current route is visible on narrow screens.
- Fixed mobile horizontal overflow classes:
  - added `min-w-0` to `PageShell`, Research Center side/main layout, and
    glass containers.
  - converted implicit single-column grids to explicit `grid-cols-1`, avoiding
    CSS Grid auto-track expansion when long evidence text/URLs appear.
  - fixed `/knowledge` list cards so actions drop to their own mobile row.
  - fixed `/research` console grid so the conversation list does not create a
    1200px implicit mobile column.
- Improved `/collector` mobile source management layout by rendering source
  rows as stacked mobile cards; the desktop/tablet table remains available at
  `sm` and above.

Validation run:

```bash
npm run lint
npm run test:frontend
npm run build
git diff --check
```

All passed. Additional Puppeteer design audit checked 10 main routes in mobile
light/dark mode for actual horizontal scroll, visible overflow, and
`af-glass-orb-btn` misuse: 20 checks, 0 issues. Visual spot-check screenshots
were captured to `/tmp/af-research-mobile-nav-fixed-2.png` and
`/tmp/af-collector-mobile.png`.

Notes:

- The worktree remains intentionally dirty from prior P2/P2.3 slices and older
  screenshot/doc updates. No commit, tag, or push was made.
- The attached file
  `/Users/chenhaorui/Downloads/china-digital-human-application-best-practices-2024-2026.zh-CN.md`
  was not modified; it was not part of Anti-FOMO source.

## 18. Immediate Recommended Next Task

The current engineering slice is complete and uncommitted. The next required
gate is an external human-review action:

```text
Complete independent post-change review for dataset 1.2.0
```

Required sequence:

1. Have an independent domain reviewer complete the 79-row second-confirmation
   sheet and all 100 formal review entries.
2. Do not fill reviewer identity, decisions, notes, or attestation on the
   reviewer's behalf.
3. Finalize and validate the review artifact.
4. Obtain an explicit provider budget before any live evaluation.
5. Start live validation with one case or one five-case batch, never the full
   suite by default.

If product development continues before external review is available, take the
next roadmap slice instead:

```text
Architecture delivery exports: ADR table, dependency workshop checklist,
stakeholder brief, and customer technical workshop agenda
```
