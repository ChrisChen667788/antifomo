# Anti-FOMO Version Iteration Plan

Updated: 2026-07-13

Status note: this file preserves the original sequencing decisions. The authoritative current release map is `docs/release-history-and-feature-map.md`; the modular refactor and day/night work below were completed across `1.1.0`, `1.5.0`, and `1.6.0`, while the `1.2.0` and `1.3.0` version numbers were subsequently assigned to the LangChain adapter and executable evaluation baseline.

Version rule: use `MAJOR.MINOR.PATCH+YYYYMMDD`, for example `0.3.1+20260423`.

## Next Version Stability Baseline: Core Subfunction Availability

Added: 2026-06-24.

Goal: treat service availability and subfunction stability as a release gate, not a manual afterthought. The immediate trigger was a Safari test where the frontend was running on `3010` but the backend research API on `8000` was not listening, causing the research card to show “研究服务暂时不可用”.

Scope:

- Add fast backend API smoke coverage for page-backing endpoints: feed items, knowledge, collector, research workspace, source settings, daily brief, retrieval status, watchlists, and focus session lifecycle.
- Add live running-service smoke coverage for the same read surfaces so “frontend up, backend down” fails explicitly without polluting local data.
- Keep long-running or paid research generation out of the default smoke path; validate that with existing research evaluation commands after budget/credentials are confirmed.
- Make Safari manual testing start with backend health and stability smoke checks.

Acceptance:

- `npm run test:backend` includes the new API stability smoke regression.
- Default read-only `npm run stability:smoke` passes before handing the app to the user for quick UI testing.
- `npm run test:backend` covers the small write-path stability regression against an isolated in-memory database; live write smoke is optional via `npm run stability:smoke -- --include-write`.
- Any 5xx or connection failure on a core page-backing endpoint blocks the release until fixed or explicitly documented.

Delivery note: the originally staged `0.3.2+20260424`, `0.3.3+20260425`, and `0.4.0+YYYYMMDD` work was implemented in order and shipped together as `0.4.0+20260423` because the actual implementation date is 2026-04-23.

## 0.3.1+20260423: Research Quality Profile

Goal: make every research report explicitly score professional rigor, intelligence value, actionability, and evidence strength.

Scope:

- Add an industry methodology playbook layer for government cloud, compute/LLM infrastructure, AI applications, and generic B2B solution research.
- Add report-level quality profile with dimension scores, strengths, gaps, and next actions.
- Add section-level evidence packs so weak chapters are visible before export or follow-up.
- Surface the quality profile in API types and the report card UI.

Acceptance:

- A generated or rewritten report contains `quality_profile`.
- Weak professional/intelligence dimensions produce concrete next actions.
- Section evidence gaps are linked to evidence quota and official-source counts.

## 0.3.2+20260424: Section Retrieval Packs

Goal: raise report factual density by feeding each important chapter with its own retrieval pack.

Status: delivered in `0.4.0+20260423`.

Scope:

- Build section retrieval targets from methodology axes.
- Route research retrieval index hits into chapter-specific evidence packs.
- Add context compression for official/procurement/source excerpts before generation. Current delivery exposes compressed snippets in section retrieval packs; generation-time injection remains a later optimization.
- Generate follow-up delta packs from supplemental evidence and previous report sections. Report-section routing shipped earlier; `0.6.4+20260513` adds offline delta evaluation and operator-facing diagnostics for the same path.

Acceptance:

- Follow-up mode identifies changed sections instead of restating the full report. Pending deeper follow-up-delta integration.
- Each key chapter receives a ranked evidence pack before generation.
- Reports with weak packs are visible through pack status and next steps; automatic generation-time downgrade remains a later packaging optimization.

## 0.3.3+20260425: Golden Report Evaluation

Goal: make quality improvement measurable.

Status: delivered in `0.4.0+20260423`.

Scope:

- Add golden sample cases for government cloud, compute infrastructure, and AI application research.
- Track professional score, intelligence value score, target-account support, official-source ratio, and section evidence pass rate.
- Add CLI and API evaluation summaries for regression runs. Current delivery provides API/service evaluation; CLI wrapper remains optional.

Acceptance:

- `npm run check` keeps unit coverage.
- A separate evaluation command reports quality deltas for golden samples. Current service/API reports baseline metrics; historical delta storage remains a later enhancement.
- New retrieval/rerank changes must not lower core quality metrics without an explicit note.

## 0.4.0+YYYYMMDD: Persistent Research Retrieval Index

Goal: turn the current in-memory minimal index into a maintainable retrieval asset.

Status: delivered as `0.4.0+20260423`.

Scope:

- Persist chunks, parent-child links, metadata, and index schema version.
- Add incremental re-index and checkpointed rebuild.
- Add optional vector backend adapter while keeping local sparse+dense fallback. Current delivery keeps the storage boundary explicit for later Milvus/vector adapter work.
- Bring watchlist, commercial hub, archive recap, and knowledge account context into the same retrieval substrate. Current index covers research reports, report versions, compare snapshots, markdown archives, and knowledge entries.

Acceptance:

- Index rebuild can resume after interruption.
- Search can filter by document type, topic and source tier in service code; API currently exposes query/topic/limit and can be expanded for all filters.
- Generated reports and exports can cite index chunk IDs.

## 0.4.3+YYYYMMDD: Follow-up Delta Routing

Goal: make follow-up research runs visibly rework only the chapters affected by new evidence, new requirements, or narrowed target-account scope.

Status: delivered as `0.4.3+20260502`.

Scope:

- Add follow-up section impact diagnostics so every follow-up run lists impacted chapters, reasons, support score, and next action.
- Distinguish whether the final report title and executive summary stayed with the baseline draft or were corrected by the follow-up pass.
- Feed impacted-section hints into generation so follow-up mode rewrites the right chapters instead of flattening the full report.
- Surface impacted chapters and changed focus in report cards and follow-up workspace UI.

Acceptance:

- A follow-up run returns a structured list of impacted sections instead of only generic follow-up diagnostics.
- Users can see which sections changed because of new scope, new evidence, or new target-account constraints.
- Follow-up mode prioritizes affected sections in prompt context rather than treating the whole report equally.

## 0.5.0+YYYYMMDD: Unified Research Retrieval Substrate

Goal: turn the retrieval index into a shared substrate across reports, watchlists, compare snapshots, archive recap, and knowledge-account context.

Status: first wave delivered as `0.5.0+20260502` (cross-surface indexing + knowledge cleaning + entity quality). Follow-up closed in `0.5.2+20260507` with schema v2 chunks, sentence-window chunks, stable chunk IDs, parent-child report links, and broader API filters. Incremental rebuild visualization and parent-block routing boost shipped in `0.6.0+20260508`.

Scope:

- Bring watchlist refresh payloads, compare/export recap, commercial hub, and account context into the same retrieval index boundary.
- Add parent-child chunking, sentence-window chunks, richer metadata payloads, and stronger document-type filters.
- Keep stable chunk IDs across re-index so downstream compare/export can cite the same evidence anchors over time.
- Expose broader retrieval filters in service and API layers for topic, document type, source tier, and perspective.

Acceptance:

- One query can return cross-surface evidence blocks spanning research reports, knowledge entries, compare recap, and watchlist output.
- Compare/export and report delivery can cite chunk IDs without time drift after rebuild or resume.
- Incremental rebuild keeps document lineage stable enough for evidence appendix reuse.

## 0.5.1+YYYYMMDD: Retrieval Quality and Official-Source Biasing

Goal: materially raise professional rigor and intelligence value by improving what evidence is retrieved, compressed, and promoted.

Status: baseline delivered as `0.5.1+20260502` (CRAG retrieval correction profile + generation grounding review + report self-evaluation profile covering faithfulness / answer relevancy / context coverage / citation quality / entity recall). Follow-up advanced in `0.5.2+20260507` with a feature-flagged local cross-encoder-style reranker and offline official-source / unsupported-target metrics, then upgraded in `0.6.0+20260508` with a lazy SentenceTransformers CrossEncoder adapter and offline reranker official-source Recall@5.

Scope:

- Add reranker and context-compression hooks on top of the current hybrid retrieval baseline.
- Keep RRF as low-cost candidate generation for sparse + dense + scope signals; do not replace it globally at this stage.
- Add an optional `cross-encoder` top-k reranker behind feature flags for report-section retrieval, official-source promotion, and account-support verification. This is the default reranker path to validate first.
- Evaluate `cross-encoder/ms-marco-*` style rerankers against offline metrics including retrieval hit rate, target-account support rate, and section evidence pass rate before rollout.
- Strengthen routing boost for parent blocks, official sources, recency, target-account anchors, and procurement/budget signals.
- Continue suppressing bogus orgs, weak vendor push pieces, fake contact channels, and unsupported target-account claims.
- Expand region, industry, buyer, and scene suffix handling so vertical-scenario research stays within hard scope.

Acceptance:

- Official-source hit rate and target-account support rate trend upward on the offline panel.
- Bogus org rate and unsupported target-account rate trend downward.
- Section evidence packs show better support density without increasing scope drift.

## 0.5.2+YYYYMMDD: Continuous Research Workspace

Goal: make the research center operate like a durable workspace with refresh, compare, and operations loops instead of a one-shot generator.

Status: first wave delivered as `0.5.2+20260507` with Watchlist operations health summary, due / overdue / stale / failed-topic diagnostics, API client types, and research-center surfacing. Follow-up shipped in `0.6.0+20260508` with run history, failed-run retry, notification summaries, and Markdown digest export.

Scope:

- Add scheduled refresh, refresh diagnostics, and recurring monitoring queue for tracking topics and watchlists.
- Compare refresh runs across time and show what changed in targets, budgets, competitors, and evidence quality.
- Add saved views, latest linked report, refresh note, and failure hints to close the operator loop.
- Keep archive diff recap, compare recap, and export artifacts aligned with refresh history.

Acceptance:

- Tracking topics and watchlists can refresh on schedule with visible failure reasons.
- Users can compare two refresh runs and quickly see net-new evidence and changed commercial posture.
- Refresh artifacts, compare recap, and export views stay linked to the same topic history.

## 0.6.0+YYYYMMDD: Advisory-Grade Delivery Chain

Goal: upgrade output from useful research notes to advisory-grade delivery materials for solution design, selling, and bidding.

Status: first wave delivered as `0.6.0+20260508` with client brief, bidding prep memo, and execution materials generated from the solution delivery pack while preserving source policy and review checklist metadata. The delivery chain was strengthened in `0.6.2+20260513` with China-tech delivery quality review, proposal/feasibility self-audit, and structural self-repair before export.

Scope:

- Standardize client briefing, bidding prep memo, ecosystem outreach memo, and executive brief around the same section-level evidence packs.
- Keep feasibility study, project proposal, and client PPT outline tied to evidence anchors, insufficiency notes, and follow-up actions.
- Improve formal document tone, section ordering, and delivery templates for external-facing use.
- Ensure export chains preserve evidence appendix, official-source ratio, and unsupported-claim warnings.

Acceptance:

- Exported delivery artifacts can be traced back to section evidence and next-step verification paths.
- Formal documents no longer hide evidence gaps behind polished wording.
- Compare/export, follow-up delivery, and advisory templates share the same frozen evidence basis.

## 0.6.1+20260510: Quality-Triggered Public Evidence Expansion

Goal: when research quality is only average, expand public evidence beyond configured source settings before generating higher-stakes advisory materials.

Status: delivered as `0.6.1+20260510`.

Scope:

- Trigger public-source expansion when report evaluation remains watch/fail or source support is too weak for delivery materials.
- Search procurement, public-resource, official, disclosure, open-web, and public WeChat channels outside the active source-setting boundary.
- Merge new evidence, rebuild diagnostics and advisory materials, then re-evaluate quality before exposing the result.

Acceptance:

- Watch/fail reports can add public evidence without manual source reconfiguration.
- Delivery materials are regenerated from the merged evidence basis rather than from the weaker first-pass pack.
- The report card exposes expansion rounds, added sources, query plan, and score movement.

## 0.6.2+YYYYMMDD: Evaluation, A/B, and Performance Control Plane

Goal: make quality improvement and retrieval/runtime optimization measurable, repeatable, and safe to iterate.

Status: first control-plane tranche delivered as `0.6.2+20260513` with solution-delivery and proposal-grade quality review, auto-repair, export audit notes, and UI surfacing. `0.6.3+20260513` then wired delivery pass rates and self-review gain rates into offline regressions, weak-sample surfacing, and compare-snapshot compatibility. `0.6.4+20260513` closed the next control-plane tranche with query/routing/reranker diagnostics, follow-up delta offline evaluation, delivery export trend/version comparison, and runtime rebuild/cache/recovery visualization. `0.6.5+20260513` hardened that surface into a persisted experiment orchestration layer with configurable plans, frozen cohorts, locked version baselines, and rollout gate decisions. `0.6.6+20260513` added the rollout audit layer: bounded gate history, promoted/revoked rollout manifests, activation payloads, and UI actions for confirming or withdrawing allowed strategy rollouts. `0.6.7+20260513` added the active policy registry and same-lane supersede behavior so promoted manifests resolve to a single current strategy per experiment lane. `0.6.8+20260514` adds a runtime strategy snapshot that turns active policies into explicit query/routing/reranker config with provenance, version-drift warnings, and UI visibility. `0.6.9+20260514` adds an effective runtime config resolver and wires retrieval search / section retrieval packs to consume promoted routing and reranker policy parameters. `0.6.10+20260514` injects query-generation and source-reranker runtime config into the report-generation pipeline and records the applied strategy in source diagnostics. `0.6.11+20260514` formalizes the GitHub release layer with full primary-surface screenshot coverage, screenshot quality gates, a generated screenshot manifest, and a release-history / feature-map document for future industry-standard updates. `0.7.0+20260518` starts the next reliability line by making Focus use the headless source collector first, adding run-level coverage metrics, and exposing source-level公众号 health diagnostics in reports, Focus, miniapp startup, and Collector Ops. `0.8.0+20260518` turns the solution delivery pack into a solution-architecture assistant with readiness scoring, blueprint layers, integration risks, non-functional requirements, stakeholder questions, and validation actions.

Scope:

- Extend offline evaluation with golden reports, low-quality queue, follow-up delta behavior, and delivery export diagnostics.
- Track retrieval hit rate, target-account support rate, section evidence pass rate, official-source recall@k, bogus org rate, unsupported target-account rate, and delta evidence yield.
- Add A/B hooks for chunking, reranking, query planning, routing policy, and official-source bias.
- Evaluate `ColBERTv2` / `PLAID` only after the persistent retrieval substrate is stable enough to support a heavier multi-vector index. Treat it as a retrieval-engine upgrade candidate, not a drop-in reranker replacement for the current local RRF path.
- Improve performance with embedding/cache reuse, incremental re-index, checkpointed rebuild, and batched recovery tooling.

Acceptance:

- Retrieval and generation changes can be judged on fixed quality metrics instead of ad hoc inspection.
- Backfill, rebuild, and rewrite jobs are restartable and measurably faster.
- The project can iterate on report quality, evidence quality, and export quality with explicit regression guards.

## 0.7.0+20260518: Focus Collection Reliability and Source Health Operations

Goal: make daily公众号 refreshes diagnosable by source, so Focus mode can keep collecting useful articles even when the WeChat PC article-window path is unavailable or incomplete.

Status: delivered as `0.7.0+20260518`.

Scope:

- Shift Focus start/resume to ensure the headless source collector daemon is running first.
- Keep the WeChat PC agent as a supplementary URL harvester rather than the only collection path.
- Persist collector run coverage metrics: handled count, coverage rate, body success rate, and coverage state.
- Persist per-source summaries for scanned, queued, collected, deduplicated, skipped, failed, and discovered articles.
- Classify each source as good, watch, or poor, with recommendations that distinguish failed discovery, stale coverage, skipped seen links, and unscanned sources.
- Surface source health in the backend daemon status, web Focus card, Collector Ops panel, and miniapp fallback response.
- Refresh GitHub-facing screenshots, release history, whitepaper, and commercial launch copy for the reliability release.

Acceptance:

- Focus mode can start the source collector daemon without waiting for the WeChat PC agent path.
- A collector status response includes `source_health`, `poor_source_count`, `watch_source_count`, coverage rate, and body success rate.
- Operators can identify which公众号 source is stale or failing instead of only seeing aggregate coverage.
- Release documentation and screenshot manifest use `0.7.0+20260518`.

## 0.8.0+20260518: Solution Architecture Readiness for Consultants

Goal: make generated solution packs visibly more useful to solution architects and industry consultants by turning research evidence into architecture boundaries, integration risks, non-functional requirements, and client validation actions.

Status: delivered as `0.8.0+20260518`.

Scope:

- Add `solution_architecture_readiness_v1` to every generated solution delivery pack.
- Score business alignment, architecture completeness, integration readiness, security/compliance readiness, and delivery feasibility.
- Generate architecture blueprint sections for business/role, application capability, model/data/integration, and security/deployment/operations layers.
- Add non-functional requirements, integration risks, assumptions, stakeholder questions, and validation actions.
- Surface architecture readiness in the research report card and solution delivery markdown export.
- Reposition README, whitepaper, launch kit, growth copy, release history, and screenshot coverage around solution architects and industry consultants.

Acceptance:

- `build_solution_delivery_pack` returns architecture readiness with non-zero score, blueprint sections, risks, and validation actions.
- Solution delivery markdown includes a dedicated `解决方案架构就绪度` chapter.
- Research report card renders architecture readiness inside the delivery pack surface.
- Version metadata and release docs use `0.8.0+20260518`.

## 0.8.1: WeChat Favorites Import and Review Queue

Goal: make personal WeChat Favorites a first-class intake path that can turn public-account favorites into recoverable homepage triage cards.

Status: delivered as part of `1.0.0+20260520`.

Scope:

- Add one-click WeChat Favorites preview and import for exported HTML/TXT, clipboard text, multi-file shortcut drops, `.url` / `.webloc`, and raw / escaped / encoded `mp.weixin.qq.com` links.
- Normalize WeChat article URLs, remove tracking query parameters, deduplicate existing items, and route public-account URLs through URL-first extraction.
- Convert imported candidates into homepage cards that follow the existing swipe / ignore / save flow.
- Persist import batches with item IDs, result payload, source summary, counts, and processing state so the latest unfinished queue can recover after reload.
- Add batch list/detail APIs, item-id filtered feed refresh, failed-item retry, and done-count tracking based on ignore/save feedback.
- Document the import path, limitations, and release validation.

Acceptance:

- A user can paste or select WeChat Favorites exports, preview recognized candidates, import them, and immediately see the latest batch on the homepage.
- Refreshing the page restores the latest unfinished batch from the backend even if local item IDs were lost.
- Failed imported items can be retried as a batch.
- Ignored or saved imported cards disappear from the active queue and count toward done.

## 0.9.0: Solution Architect Workbench

Goal: move the solution delivery pack from architecture readiness assessment into customer-meeting preparation, so architects and consultants can see the scenario, stakeholders, decision criteria, and validation path in one place.

Status: delivered as part of `1.0.0+20260520`.

Scope:

- Add `solution_architect_workbench_v1` to generated solution delivery packs.
- Generate customer scenarios with target customer, primary roles, pain points, desired outcomes, success metrics, and evidence.
- Map likely stakeholders such as business owners, information/technology teams, security/compliance reviewers, and procurement/budget owners to concerns, decision questions, and required materials.
- Generate decision criteria for business value, system integration/data availability, security/compliance/deployment shape, and procurement/delivery rhythm.
- Add next-meeting agendas and export the workbench into solution delivery markdown.
- Surface the workbench inside the research report card next to architecture readiness.

Acceptance:

- `build_solution_delivery_pack` returns `architect_workbench` with customer scenarios, stakeholders, decision criteria, and next-meeting agenda.
- Solution delivery markdown includes `解决方案架构师工作台`, `干系人问题地图`, and decision validation actions.
- The research report card renders the workbench inside the delivery pack surface without hiding the existing architecture readiness panel.

## 1.0.0+20260520: Local-First WeChat-to-Solution Baseline

Goal: mark the first complete local-first baseline where WeChat-heavy intake, homepage triage, evidence-backed research, solution architecture readiness, architect workbench output, and release validation are connected end to end.

Status: delivered as `1.0.0+20260520`.

Scope:

- Ship WeChat Favorites one-click preview/import with URL/text parsing, escaped-link normalization, deduplication, persistent batches, queue recovery, failed-item retry, and swipe-based ignore/save triage.
- Ship the solution architect workbench with customer scenarios, stakeholder question maps, decision criteria, validation actions, and next-meeting agendas.
- Add the Alembic migration and SQLite compatibility path for `collector_import_batches`.
- Cover parser, service, API restoration, SQLite compatibility, solution-intelligence, markdown export, frontend lint, production build, demo smoke, and diff hygiene in release validation.
- Align package metadata, changelog, README, release history, whitepaper, launch copy, screenshot coverage docs, and screenshot manifest to `1.0.0+20260520`.

Acceptance:

- A fresh database can be migrated with the collector import batch table available.
- A legacy SQLite database can auto-create the same table through compatibility setup.
- A user can import WeChat Favorites, reload the homepage, recover the latest unfinished batch, retry failures, and process cards through ignore/save.
- Generated solution delivery packs include architecture readiness plus the architect workbench in API responses, UI, and markdown export.
- Release validation commands pass before the user is told 1.0 is complete.

## 1.1.0: Architecture Decisions and Dependency Diagnostics

Goal: move the solution architect workbench from meeting-prep checklists into architecture-review artifacts that can drive customer technical workshops and internal solution reviews.

Status: delivered as part of `1.1.0+20260602`.

Scope:

- Add capability-to-architecture mappings that connect business capabilities to application services, data dependencies, model dependencies, integration surfaces, security constraints, evidence, and validation actions.
- Add ADR-style architecture decision records with context, options, selected direction, tradeoffs, risks, and validation evidence.
- Add integration dependency diagnostics for source systems, API/data contracts, auth boundaries, deployment assumptions, operational owners, risk level, and validation actions.
- Surface these workbench artifacts in solution delivery markdown and the research report card without hiding existing customer scenarios, stakeholder maps, and decision criteria.

Acceptance:

- `build_solution_delivery_pack` returns `architect_workbench.capability_architecture_matrix`, `architecture_decision_records`, and `integration_dependencies`.
- Solution delivery markdown includes `能力到架构矩阵`, `ADR 架构决策记录`, and `集成依赖诊断`.
- The research report card renders the new architecture-review artifacts inside the existing delivery-pack surface.

## 1.2.0: Modular Architecture Refactor

Goal: reduce coupling before the next feature expansion by separating orchestration, domain logic, persistence, external adapters, and UI features into clearer modules.

Status: completed across `1.1.0`, `1.5.0`, and `1.6.0`. Detailed execution log: `docs/current-version-and-refactor-roadmap-2026-05-20.md`.

Principles:

- Preserve conceptual integrity and avoid broad rewrites.
- Keep public behavior and API response shape stable unless a route is explicitly versioned.
- Move logic by workflow slices, backed by tests before and after each slice.
- Favor high-cohesion feature modules over generic utility piles.

Scope:

- Produce a dependency and ownership map for backend services, API routers, frontend routes/components, and API clients.
- Split backend service hubs into `api`, `application`, `domain`, `persistence`, and `infrastructure` concerns where the current file size/coupling justifies it.
- Move collector import parsing/batch persistence, item processing, research delivery generation, architecture workbench, experiments, knowledge, and execution workflows behind explicit entrypoints.
- Split frontend API clients and feature state into feature modules while keeping compatibility exports during migration.
- Extract shared UI primitives and reduce route-level business logic.

Acceptance:

- Core workflows still pass: WeChat Favorites import, item triage/reprocess, research generation, solution delivery export, focus/session operations, knowledge operations.
- `npm run lint`, `npm run build`, `npm run test:backend`, and `git diff --check` pass after each migration tranche.
- New module boundaries are documented and cross-module dependency violations are either prevented or explicitly listed as debt.

## 1.3.0: Day/Night Design System Refresh

Goal: make light mode and dark mode distinct, polished visual systems instead of a shared glass UI with variable swaps.

Status: completed across `1.1.0` and the `1.6.0` release-hardening line. Detailed execution log: `docs/current-version-and-refactor-roadmap-2026-05-20.md`.

Scope:

- Introduce semantic theme tokens for page, shell, surfaces, elevation, text, borders, focus rings, status colors, and accents.
- Replace hard-coded light Tailwind color classes in shared components and primary product surfaces.
- Rebuild dark mode around a deep neutral base, lower glare, clearer hierarchy, purposeful accents, and stronger panel separation.
- Migrate layout/nav, feed, inbox/research report card, collector, settings, knowledge, and research center in controlled slices.
- Add dark-mode screenshot capture or verification coverage for primary surfaces.

Acceptance:

- Night mode has a visibly distinct design language with readable hierarchy and no major light-surface leakage.
- Text, badges, buttons, panels, forms, and selected/hover/disabled/focus states remain readable in both modes.
- Production build, lint, and screenshot checks pass before release.

## Next Priority Insert: Financial-Scope Guardrails and China IT Delivery Artifacts

Goal: raise generated solution decks and consulting documents to a China tech/IT pre-sales delivery baseline, while preventing cross-industry leakage such as medical/culture-tourism accounts appearing in finance-topic reports.

Status: inserted after the current stability/UI cleanup line; backend finance-scope guardrails and first UI detail fixes started in the next working version.

External references reviewed:

- GitHub `PptxGenJS`: native editable PPTX generation from JavaScript with charts, tables, images, shapes, templates, and OOXML-compatible output. Candidate for replacing screenshot-like deck output with editable corporate slides.
- GitHub `python-pptx`: Python library for creating, reading, and updating PowerPoint files. Candidate for backend-side PPTX inspection and compatibility regression tests.
- GitHub `python-docx-template/docxtpl`: Jinja2-style DOCX template rendering. Candidate for China IT proposal/feasibility report templates where section structure and Word styles must be controlled.
- GitHub `Gotenberg`: Docker PDF conversion API with Chromium and LibreOffice included. Candidate for Office-to-PDF roundtrip tests once local/container dependency is available.
- ModelScope `MinerU`: PDF/DOCX/PPTX/XLSX/image to Markdown/JSON extraction. Candidate for imported reference proposals and generated artifact QA.
- ModelScope `FinGPT` and BGE/Qwen rerankers: candidates for finance-domain source reranking and finance-language consistency checks.
- Skill-style PPT workflows from MiniMax-AI/skills, anthropics/skills, and community Office skills: useful process patterns are template analysis, outline JSON, slide content JSON, OOXML edit/pack, overlap validation, and machine-readable QA gates.

Current gaps observed:

- UI detail debt: long evidence/quality rows wrap with inconsistent bullet alignment; some small badges look like floating debug remnants; repeated classes and dense helper text create noise.
- Scope debt: industry scope is not yet a first-class guard in every report merge path. Region conflict exists, but finance reports can still retain medical/culture-tourism rows if LLM output or fallback intelligence provides them.
- Delivery artifact debt: solution delivery markdown and PPTX still expose internal workbench language, placeholders, weak evidence snippets, and generic outline terms; generated structure does not yet match common China IT proposal/可研/项目建议书 conventions.

Implementation order:

1. P0 guardrails: add scope-aware industry conflict filtering for final report fields, ranked fallback entities, public contacts, account team rows, source-intelligence fallback rows, and stored-report rewrite.
2. P0 regression: add finance-topic tests asserting `申康医院发展中心`、`上海市卫生健康委`、`上海市文化和旅游局` cannot survive in finance target/contact/team fields, while `上海市委金融办`、`上海证券交易所` remain valid.
3. P1 UI cleanup: align bullet wrapping, replace floating/vertical micro badges with conventional pills, remove duplicated class noise, and continue a full pass over visible customer-facing copy.
4. P1 document compiler: define China IT artifact schemas:
   - 解决方案: 封面、目录、背景与痛点、建设目标、总体架构、业务场景、能力清单、实施路径、项目组织、风险与保障、投资与收益、附录证据。
   - 项目建议书: 项目概况、必要性、建设内容、实施计划、投资估算、效益分析、风险控制、结论建议。
   - 可行性研究报告: 编制依据、现状需求、目标范围、方案比选、推荐方案、投资估算、经济/社会效益、实施组织、风险、结论。
   - 客户 PPT: 1页结论、3页问题与机会、3页方案与架构、2页实施与价值、1页下一步。
5. P1 rendering: add editable PPTX layout tokens, master-slide-like constants, chart/table primitives, and text-overlap guards; keep existing export API but route new decks through the stricter compiler.
6. P2 QA: add Office roundtrip checks, PDF preview baselines, generated artifact text extraction, placeholder/noise scanner, and finance/medical/tourism cross-scope fixtures.

Acceptance:

- Finance-topic reports do not show medical/culture-tourism targets, public contacts, team rows, or deck/customer-facing sections unless the user explicitly asks for a cross-industry comparison.
- Generated artifacts avoid internal labels such as compiler/debug/workbench terms in customer-facing sections.
- PPTX is editable, uses consistent Chinese corporate layout, and passes no-overlap, no-placeholder, no-cross-scope, and basic Office/PDF roundtrip checks.
- DOCX/PDF outputs keep A4/Chinese font assumptions explicit and include artifact visual/text regression coverage.

## Next Quality Line: Evidence-Closed Research and Decision-Grade Solutions

Goal: fix the current topic leakage and evidence insufficiency before further model or document-polish upgrades, then make solution design traceable to measurable architecture decisions.

Status: engineering implementation is complete locally through `1.9.1` on 2026-07-13. Release promotion remains blocked by the real 100+30 expert-calibration, three-industry blind-evaluation, and customer-acceptance gates; deterministic fixtures are implementation evidence, not human approval. Detailed research, metrics, hard-negative evidence, and source links are maintained in `docs/professional-report-quality-v1.8.0.md` under `2026-07-13 外部调研结论与后续质量路线`.

Why now:

- The latest Shanghai medical-AI job retained only two unrelated Codex/OpenAI sources while reporting `strict_match_ratio=1.0`, then generated a polished but off-topic solution pack.
- This is a fail-closed and evaluation problem first. A stronger model or more elaborate template cannot repair evidence that never matched the question.

Implementation order:

| Version | Priority | Delivery focus | Release gate |
| --- | --- | --- | --- |
| `1.8.2` | P0 | Real research data binding, scope contract, source acceptance ledger, semantic reranking, index isolation, evidence minimums | Known medical hard-negative is blocked; source precision >=95%; critical cross-industry leakage = 0 |
| `1.8.3` | P0 | Question-tree research, adaptive corrective retrieval, atomic claims, counter-evidence, citation-at-draft-time | Critical claim coverage = 100%; citation support >=95%; no zero-evidence top-level question |
| `1.8.4` | P0/P1 | Multi-dimensional evaluation, hard score caps, 100-case independent review, expert calibration and baseline A/B | Undeliverable recall >=95%; no hard failure can be promoted by aggregate score |
| `1.9.0` | P1 | QAW quality-attribute scenarios, ATAM tradeoffs, ADR evidence, C4 views, Well-Architected and NIST AI risk review | Requirements-to-test traceability = 100%; no orphan component or unmeasured critical NFR |
| `1.9.1` | P1 | Proof-of-architecture artifacts, executable validation actions, customer/internal evidence split, readiness integration | Every high-risk decision has real validation evidence; medical/finance/tourism end-to-end blind review passes |

Local delivery record:

- `1.8.2`: implemented in the default research workflow with scope contracts, source admissions, evidence minimums, index/archive isolation, medical/financial routing, evidence-gap output, and hard-negative regression coverage.
- `1.8.3`: implemented with a six-axis question tree, bounded corrective retrieval, atomic claim/citation gates, fail-closed solution delivery, and release-readiness integration.
- `1.8.4`: implemented with a 100-primary/30-dual blind-review calibration workflow, arbitration and bias/recall metrics, plus one shared 20/40/59 hard-failure policy; real expert fields remain pending.
- `1.9.0`: implemented with measurable QAW scenarios, complete ATAM finding classes, three-option ADRs, five C4 views, cloud-neutral/NIST AI review, 100% traceability, and zero-orphan checks.
- `1.9.1`: implemented with machine-readable proof checks, a digest-verified three-domain minimum simulator, customer/internal evidence separation, and release-readiness gates; real blind/customer evidence remains pending.
- Promotion state: blocked until the pending expert reviewers and customer owners complete the required artifacts; the low-quality queue is 6/68 with zero invalid payloads, and machine stability, architecture, simulator, and Office gates are recorded separately from human approval.

Cross-version rules:

- A research result that fails topic, minimum-evidence, reranker, source-diversity, or citation gates produces an evidence-gap brief only. It must not produce a client-ready report or full solution blueprint.
- The solution pipeline consumes only accepted claims from the claim-evidence ledger; it must not read raw unfiltered chunks as customer-facing facts.
- Aggregate quality scores cannot override hard failures. Runtime/API/UI/diagnostics/release-readiness must expose the same blocking reason.
- Model upgrades are benchmarked per module and rolled out in shadow mode, then 5%, 25%, and 100% stages. “Strongest model” routing is not a substitute for retrieval and evidence gates.

## Post-1.9.1 Product Line: Source-Grounded Knowledge and Decision Documents

Status: locally implemented through `2.0.6-development` on 2026-07-16. The engineering contracts, APIs, migrations, tests, and `/studio` surface below are present, but none of these versions is release-approved. The existing `1.8.4-1.9.1` expert, blind-review, customer, Office, visual, and release-readiness blocks remain authoritative, and the new human-qrels, production-signing, permission-leakage, performance, recovery, and cross-artifact acceptance gates remain open.

Competitive and open-source research, code-level gap analysis, schemas, APIs, metrics, license boundaries, and per-version acceptance criteria are maintained in `docs/knowledge-product-competitive-research-and-roadmap-2026-07-16.md`.

Positioning:

- Do not compete as a generic chat knowledge base. Preserve the product chain: WeChat/Web/file signals -> controlled evidence -> China-specific research/solution/feasibility/project-proposal artifacts -> executable architecture and acceptance evidence.
- Adopt NotebookLM-style source selection and passage click-back, Notion-style permission-aware knowledge governance, WorkBuddy-style governed task/artifact flow, and ima-style low-friction China content intake without bypassing the current fail-closed evidence model.

Implementation order:

| Version | Priority | Delivery focus | Engineering status | Release gate |
| --- | --- | --- | --- | --- |
| `1.9.2` | P0 | True Chinese semantic retrieval, document parser adapters, source revisions, passage citations, Sources/Chat/Studio Notebook | Implemented locally; production-model artifact and human qrels pending | 300-query human qrels; nDCG@10 >=0.78 and >=15% above hash baseline; Recall@20 >=0.90; citation click-back >=98%; excluded-source leakage = 0 |
| `1.9.3` | P0 | Versioned China decision-document contracts, 2023 government/enterprise feasibility policy packs, field-state and formula lineage | Implemented locally; real expert document samples pending | Applicable official-outline coverage = 100%; unsourced generated numbers = 0; formula/export consistency = 100%; real expert samples remain mandatory |
| `1.9.4` | P0/P1 | Claim graph, bounded chapter writers, consistency challenger, dependency DAG and incremental section rebuild | Implemented locally; large-corpus rebuild benchmark pending | Critical claim citation = 100%; critical cross-chapter conflicts = 0; >=90% unaffected sections avoid rebuild |
| `1.9.5` | P1 | Knowledge spaces, document ACL, verified owner/expiry, review threads, controlled connectors and artifact backflow | Implemented locally; cross-surface permission matrix pending | Permission leakage = 0 across search/chat/cache/export/deep-link tests; revoked or expired evidence cannot support new critical claims |
| `1.9.6` | P1 | Signed Skill registry, permission manifest, quarantine/dry-run/benchmark, governed MCP and first-party research/document skills | Implemented locally; production signing key and real benchmarks pending | Unsigned/unlicensed/over-privileged Skills cannot be approved; prompt-injection fixtures produce zero undeclared actions |
| `2.0.0` | P1 | Evidence-bound audio brief, mind map, data table, slide/infographic Studio plus commercial performance/security readiness | Implemented as development line; commercial promotion blocked | Cross-artifact critical consistency = 100%; all existing human/customer/Office/visual/security gates pass before promotion |

Implementation evidence added in this line:

- `backend/app/services/decision_studio/` owns parsing, embeddings, Notebook/source revisions, formal-document contracts, Claim/section compilation, Knowledge Space governance, Skills, artifacts, and readiness.
- `/api/decision-studio` exposes the workflow through typed FastAPI requests; `/studio` is the operational Next.js surface.
- Alembic revision `20260716_0026` is forward/backward tested on an isolated SQLite baseline.
- Deterministic tests cover source selection leakage, passage click-back, stale citation blocking, formula lineage, conflict blocking, incremental compilation, ACL, connector/Skill permission rejection, artifact consistency, and inherited release blocking.

Cross-version rules for this line:

- The existing deterministic hash vector remains a reproducible baseline but must not be presented as production semantic retrieval after `1.9.2`.
- Every citation stores an immutable source revision and passage coordinate; a URL alone is not a sufficient citation anchor.
- Every formal-document field is explicit evidence, calculated data, assumption, missing information, or not applicable. Models must not silently turn missing fields into facts.
- Every artifact is built from accepted claims and carries source, policy, model, parser, and Skill revisions. A dependency change marks affected artifacts stale.
- Third-party parsers, models, frameworks, and Skills require provenance, pinned revision, license snapshot, security review, benchmark evidence, and rollback before production use.

## 2.0.1-2.0.6 Release Program Extension

Status: locally implemented on 2026-07-16. These versions complete the engineering paths and acceptance calculators; they do not change the authoritative `blocked` commercial status.

| Version | Engineering delivery | Current acceptance state |
| --- | --- | --- |
| `2.0.1` | Existing knowledge/report activation, three-domain qrel calculator, parser fidelity calculator | Blocked pending 300 human qrels and 100 real parser samples |
| `2.0.2` | Three formal-document calibration contract and Claim/incremental-compiler acceptance | Blocked pending 60 expert documents and raw compiler benchmark artifact |
| `2.0.3` | 100-report independent-review and 500-entity authenticity calculators | Blocked pending independent reviewer artifacts and attestations |
| `2.0.4` | Cross-surface permission matrix and five-Skill security benchmark contract | Blocked pending production security review and raw matrix/benchmark artifacts |
| `2.0.5` | Six-form consistency contract and Office/Studio visual acceptance | Blocked pending Office roundtrip and independent light/dark visual approval |
| `2.0.6` | Performance/cost plus queue/backup/audit/external-volume recovery contracts | Blocked pending production-like load, backup restore, and failure-injection evidence |

All suites append immutable evidence to `decision_validation_runs`; the aggregate uses each suite's latest run and preserves all inherited human, expert, blind-review, customer, Office, and visual blockers. See `docs/decision-studio-release-program-v2.0.1-v2.0.6.md` for exact thresholds and operator commands.

## 2.0.7-2.2.0 Competitive-Informed Decision Program

Status: locally implemented through `2.2.0-development` on 2026-07-18 under an explicitly authorized non-release development branch. The roadmap is based on the official-source comparison in `docs/competitive-landscape-and-post-2.0.6-roadmap-2026-07-17.md`. Engineering completion does not mark any version release-approved: the immutable RC, human qrels, parser corpus, independent Office review, enterprise connector matrix, vertical expert artifacts, and three customer signoffs remain blocked until real evidence is submitted.

Strategic correction:

- Deep research with citations, internal-knowledge search, connectors, and multiform artifacts are now broadly available across domestic and international products. They are necessary capabilities, not a durable differentiator by themselves.
- Preserve the differentiated chain: controlled source snapshot -> Claim Graph -> Chinese formal decision-document compiler -> architecture tradeoffs -> executable acceptance evidence.
- Do not start broad feature expansion while the existing real human, customer, Office, visual, security, performance, and recovery gates remain blocked.

Implementation order:

| Version | Priority | Delivery focus | Required release gate |
| --- | --- | --- | --- |
| `2.0.7` | P0 | Release Evidence Closure: freeze the RC digest and complete human qrels, parser samples, expert documents, independent report/entity review, three-industry blind review, customer acceptance, permission/Skill security, Office/visual, load/cost, backup/recovery, and external-volume evidence | Every inherited and Decision Studio suite passes against the same immutable digest; invalid payloads = 0; low-quality flagged rate <=10%; no fixture counted as external approval |
| `2.1.0` | P0 | Research Control Room: approved brief/question tree, source candidate inbox, accept/reject/lock, frozen source bundles, live steering, budget/progress, pause/resume, and run comparison | Approved-plan conformance >=95% on 30 real tasks; rejected-source leakage = 0; restart recovery preserves snapshot, budget, claims, and audit |
| `2.1.1` | P0 | Retrieval and Parsing Quality: hybrid retrieval, measured reranking, Docling/MinerU shadow routing, table/formula/image coordinates, drift and resource monitoring | >=600 adjudicated qrels; nDCG@10 >=0.82; Recall@20 >=0.92; critical cross-industry false positive <=1%; citation click-back >=99% on >=200 documents |
| `2.1.2` | P1 | Evidence-Aware Decision Document Editor: structured editing, source/claim/formula/policy side panel, human-edit preservation, comments/approval, editable charts/tables, partial rebuild, and Office profiles | Unsupported numbers = 0; formula and critical-claim coverage = 100%; unaffected edit preservation >=99%; independent Office and visual gates pass |
| `2.1.3` | P1 | Enterprise Identity and Connectors: OIDC/OAuth/SSO, tenant roles, read-only Feishu/Tencent Docs/Notion/Microsoft 365 pilots, native ACL sync, revocation/deletion, writeback preview, retention and audit | Permission leakage = 0 across every surface; revocation meets documented SLA; credentials never enter logs/prompts/traces/exports; connector failure matrix passes |
| `2.1.4` | P1 | Governed Agent Operations: durable runs, checkpoints, idempotency, schedules, budgets, approval nodes, production signatures, dry-run effects, replay and rollback | Undeclared actions = 0 across >=100 injection/confused-deputy cases; every high-risk action has exact human approval; restart creates no duplicate effects |
| `2.1.5` | P1 | Vertical Evidence Packs: healthcare, finance, and culture-tourism official/licensed source registries, ontologies, document contracts, formulas, risks, hard negatives and expert rubrics | Each sector has >=100 benchmark tasks and >=30 expert-reviewed artifacts; critical official-source coverage >=95%; entity precision >=98%; cross-industry leakage = 0 |
| `2.2.0` | P0 commercial | Commercial Team Decision OS: multi-user decisions/reviews, deployment/admin/retention/DR/SLA/billing, and three complete vertical pilots | All inherited gates pass; >=3 real customer pilots complete the full evidence-to-acceptance workflow; no critical security/evidence/Office/visual/recovery/customer issue remains open |

Engineering completion map:

| Version | Implemented contract | Acceptance state |
| --- | --- | --- |
| `2.0.7` | Immutable release-candidate digest, suite binding, external-attestation validation, blocker snapshot | `blocked` until every suite binds the same digest and expert/blind/customer artifacts are real |
| `2.1.0` | Editable draft brief/question/source plan, approval hash, frozen source snapshot, budget, checkpoint, pause/resume/cancel/compare | `blocked` until representative real-run conformance and recovery evidence passes |
| `2.1.1` | Semantic/lexical/hybrid-RRF retrieval modes and immutable retrieval/parser/model/vertical benchmark records | `blocked` until 600 qrels and 200-document locked corpus meet thresholds |
| `2.1.2` | Evidence-aware blocks, optimistic revision lock, human-edit preservation, differential rebuild, DOCX/PPTX and independent visual confirmation | `blocked` until independent Office/visual artifacts and expert document reviews pass |
| `2.1.3` | Fingerprint-only enterprise identity profiles, Microsoft 365/SharePoint connector types, idempotent ACL sync snapshots and delete propagation | `blocked` until production identity, leakage, revocation, failure and recovery matrices pass |
| `2.1.4` | Durable Agent plans, budgets, checkpoints, idempotency, high-risk approvals, schedule/pause/resume/cancel and internal rollback | `blocked` until production signing and >=100 adversarial cases prove no undeclared or duplicate effects |
| `2.1.5` | Versioned medical, finance and tourism source/ontology/contract/hard-negative/rubric packs | `blocked` until each pack has >=100 tasks and >=30 real expert-reviewed artifacts |
| `2.2.0` | Space-bound customer Pilot workflow, deployment/SLA/evidence bundle, inherited readiness and customer signoff | `blocked` until accepted Pilots cover medical, finance and tourism with all inherited gates passing |

The implementation and operator contract is recorded in `docs/decision-program-v2.0.7-v2.2.0.md`.

Cross-version rules:

- The sequence is gate-driven, not calendar-driven. Merging code does not authorize the next commercial stage.
- `2.0.7` permits defect fixes discovered by evidence collection, but not broad connector, agent, editor, or artifact expansion.
- BGE-M3 remains the retrieval incumbent until a challenger wins the same human-qrel, latency, memory, cost, license, and rollback benchmark. Do not select an 8B reranker only because its public leaderboard is stronger.
- Third-party parsers and frameworks enter through quarantine, provenance/license snapshots, pinned revisions, representative benchmarks, shadow runs, and rollback proof.
- Build only the evidence-aware editor needed for decision artifacts; integrate with existing collaboration suites instead of recreating a general workspace.
- Build a small set of first-party governed Skills before considering any marketplace.
- No aggregate score, model upgrade, source count, report length, or visual polish can override a hard evidence, permission, formal-contract, or acceptance failure.

## 2.2.1-2.3.1 Research Recovery and UX Closure

Status: engineering implementation complete locally on 2026-07-26 after user testing exposed two P0 usability defects: evidence gaps terminated without an effective clarification loop, and the default report surface exposed excessive internal governance and runtime terminology. Real-task and customer acceptance remain blocked. This is release-hardening work discovered through product use, not authorization to weaken evidence gates or mark the product release-ready.

| Version | Priority | Delivery focus | Required release gate |
| --- | --- | --- | --- |
| `2.2.1` | P0 | Evidence Recovery Contract: user-facing interaction states, bounded automatic recovery, near-threshold provisional output, structured clarification packets, and formal-export protection | At least 60 cross-industry evidence-gap cases always produce recovery, a bounded draft, or actionable questions; blank terminal output = 0; hard-gate bypass = 0 |
| `2.2.2` | P0 | Guided Clarification and Resume: typed questions, URL/file/text supplementation, accepted-snapshot reuse, idempotent continuation, parent/child lineage, delta rebuild, and provenance audit | Clarification-to-field mapping >=95%; accepted-source preservation = 100%; duplicate effects = 0; user-supplied provenance = 100% |
| `2.2.3` | P0 UX | Progressive Disclosure Research UI: result-first layout, immediate recovery card, plain-language states, advanced diagnostics drawer, mobile/accessibility and visual baselines | Default UI exposes zero raw enum/version/reranker/scope-gate terms; unassisted next-action comprehension >=90%; desktop/mobile visual and accessibility gates pass |
| `2.3.0` | P0 release closure | Human-in-the-loop Research Experience RC across preflight clarification, post-search recovery, resumable updates, telemetry, experiments, and release-readiness | At least 120 real tasks across six industries; evidence-gap-to-usable conversion >=75%; median questions <=3; abandonment improves >=30%; unsupported critical claims and gate bypasses = 0 |
| `2.3.1` | P0 operations | Clarification Quality and Operations: feedback capture, stale recovery, idempotent replay, source-provenance and gate-bypass telemetry, degraded-system retry, and release-readiness integration | >=30 human feedback records; average score >=4.0; technical-copy feedback <=10%; stale recovery <=15%; formal bypass and missing provenance = 0 |

The product, API, frontend, provenance, test, and measurement contract is recorded in `docs/research-clarification-and-progressive-disclosure-roadmap-2026-07-26.md`. The `2.2.1-2.9.5` engineering slices are implemented locally, including entity-role truth, source topology, unified delivery truth, account pursuit, customer architecture traceability, calibration templates, a read-only Assurance Command Center, a 15-round retrieval-assurance and controlled-promotion chain, and a 15-round retrieval evidence-operations chain. Their external acceptance gates remain blocked, and all inherited independent expert, customer, Office, visual, security, performance, recovery, and immutable-RC blockers continue to apply.
