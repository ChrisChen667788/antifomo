# Changelog

## Unreleased

## 1.8.0+20260622 - 2026-06-22

- Started the `1.8.0` professional-report quality line and inserted it ahead of later generic delivery-export work.
- Split delivery scoring into structural and semantic dimensions, adding deterministic content-hygiene and claim-to-evidence traceability metrics.
- Added semantic hard caps so webpage/navigation contamination fails delivery review and structure-only documents without concrete evidence anchors cannot receive pass status.
- Added regression coverage for the previous false-high-score failure mode, contaminated delivery content, and traceable strong claims.
- Added a versioned claim/evidence ledger with stable claim, evidence, and issue IDs; typed support/conflict/background/validation relationships; and high-confidence evidence coverage gates.
- Added entity-role consistency checks and normalized numeric comparison across CNY units, periods, and percentages; conflicting non-scenario values now block delivery pass status.
- Exposed the ledger in solution-pack APIs, Markdown exports, formal feasibility/proposal appendices, and the research delivery summary UI.
- Added the P0.3 semantic challenger with stable `sch_*` issue IDs for scope drift, cross-section entity/numeric conflicts, source contamination, unsupported high-confidence claims, template placeholders, and golden-sample alignment gaps.
- Added versioned, de-identified real-project-style delivery golden samples for government AI service-center, tourism AIGC guide, and smart-manufacturing quality-platform scenarios, plus regression tests for scope drift, cross-section conflicts, and unsupported strong claims.
- Exposed semantic-challenger status, scores, blocking issues, and golden-sample alignment in solution-pack APIs, Markdown exports, formal feasibility/proposal appendices, and the delivery summary UI.
- Added P1.1 dedicated document compilers for solution design, consulting reports, project proposals, and feasibility studies, each with distinct section logic, assumptions, validation actions, quality gates, and Markdown output.
- Routed solution-pack outlines and formal feasibility/proposal Word/PDF exports through the dedicated compiler outputs while preserving legacy outline/API compatibility and supplemental evidence sections.
- Added the P1.2 quantitative decision model with weighted alternatives, tender scoring response matrix, three-scenario CAPEX/OPEX/TCO/benefit/NPV/IRR/ROI/payback calculations, and sensitivity variables.
- Routed the quantitative model into solution-pack APIs, Markdown exports, formal feasibility/proposal appendices, TypeScript contracts, and the research delivery summary UI while keeping missing finance inputs as explicit assumptions instead of fabricated numbers.
- Added a source-backed real-business golden sample gate for 2026 Shanghai medical AI, 2026 Shanghai culture-tourism AI, and 2026 Yangtze River Delta government AI opportunity themes.
- Registered the three real-business themes as semantic-challenger golden samples and added deterministic validation covering source integrity, four document compilers, P1.2 no-amount finance degradation, and P0.3 golden alignment.
- Hardened policy/pilot source handling so non-tender public sources no longer generate fake procurement projects or pseudo-financial estimates; delivery wording now falls back to policy/pilot opportunity preparation when no real tender evidence exists.
- Started P2 formal delivery engineering by adding controlled Word-compatible HTML and PDF-preview rendering for feasibility-study and project-proposal exports, including A4 styles, metadata tables, table of contents, stable section/appendix numbering, header/footer hooks, and round-trip checklists.
- Extended the simple PDF renderer with optional page headers and footers, and added formal-rendering regression coverage for numbering, tables, headers/footers, PDF previews, and legacy text-search compatibility.
- Added P2.2 native DOCX export for feasibility-study and project-proposal Word tasks using in-repo OpenXML generation, with `.docx` MIME types, `content_base64` artifacts, and retained HTML previews.
- Added controlled PDF render diagnostics for formal exports, including shared round-trip checklists, Chinese proofreading findings, and visual-regression fingerprints.
- Added editable PPTX solution-delivery export, backend/API/WorkBuddy task typing, frontend download support, and an Inbox button for customer-facing deck output.
- Added deterministic Chinese proofreading for formal deliverables, covering punctuation, units, spacing, brackets, overclaiming, and unresolved validation markers.
- Refreshed 30 light/dark product screenshots through the screenshot regression harness after P2.2.
- Upgraded formal DOCX output to a P2.3 professional template with executive dashboard, Word-updatable TOC field, Office settings, media layout placeholders, stronger styles, and chart/image placeholder guidance.
- Upgraded editable PPTX output with a theme, professional cards, chart and image placeholders, and customer-facing layout scaffolding.
- Added non-GUI Office round-trip validation for DOCX/PPTX/PDF artifacts, local Word/PowerPoint/QuickLook/LibreOffice capability detection, and an explicit `npm run office:roundtrip` script.
- Extended semantic dark-theme coverage to every primary product route, including the active research progress card, knowledge commercial/account surfaces, import queues, Focus, Collector, settings, and research workspaces; regenerated 30 light/dark release screenshots.
- Fixed WeChat Favorites manual-import batch persistence and stale frontend polling recovery so a returned batch remains queryable and resumes after refresh.
- Added an opt-in local WeChat Favorites auto-import adapter around `wechat-cli favorites --type article`, incremental URL deduplication, daemon diagnostics, and a visible setup/unavailable state without installing or modifying WeChat automatically.
- Hardened WeChat article extraction by waiting for the real `#js_content` body, recognizing parameter-error/verification/expired-link shells, retaining canonical URLs, and falling back instead of summarizing an error page.
- Upgraded research delivery structure with perspective-guided decomposition, cross-source contradiction checks, alternative comparison, operations, impact evaluation, evidence matrices, and NDRC-aligned feasibility/proposal outlines.
- Fixed the legacy OpenAI adapter's missing quota exception and Chinese quota detection; configured fallback credentials now take over correctly instead of forcing every report onto deterministic mock output.
- Added locked `regions` and `entities` to independent-review artifacts and immutable-context validation so the `1.7.2` scope corrections can receive meaningful post-change approval.
- Repaired `1.7.2` release metadata across the Chinese README, changelog, screenshot manifest, screenshot coverage notes, and current roadmap without recapturing unchanged UI assets.

## 1.7.2+20260615 - 2026-06-15

- Applied 78 expert scope comments to the locked research evaluation set by replacing broad or empty regions and missing research subjects with concrete province/city scopes and named targets.
- Preserved every reviewed behavior label, reference answer term, and expected source domain; kept the unanswered but already concrete `transport-003` case unchanged.
- Upgraded the dataset to `1.2.0`, removed all remaining national/global/empty region scopes, and wrote a new reproducible lock digest.
- Added an auditable scope-feedback resolution map, repeatable application script, regression coverage, and explicit documentation that applied feedback is not independent post-change approval.

## 1.7.1+20260614 - 2026-06-14

- Added independent-review template export, reviewer finalization, immutable locked-context validation, reviewer separation checks, attestations, and a review-content digest.
- Added a 100-case live-evaluation budget plan with a target ceiling of `$81.50`, split into 20 default batches of five cases.
- Required live-provider runs to provide a validated independent-review artifact and explicit approved budget, with a default maximum of five cases per invocation.
- Added immediate runtime stops when provider pricing is unavailable or observed spend exceeds the approved budget.

## 1.7.0+20260614 - 2026-06-14

- Locked all 100 research evaluation cases with explicit behavior labels, answer terms, first-party source-domain expectations, review metadata, and a reproducible SHA-256 digest.
- Added a no-network, no-model-cost deterministic/LangGraph parity gate and passed all 100 cases with equivalent reports, callbacks, snapshots, metrics, and cost ledgers.
- Promoted `langgraph` to the default research workflow engine while retaining `deterministic` as an immediate rollback and `langgraph_shadow` as a compatibility alias.
- Overrode the vulnerable PostCSS transitive dependency with `8.5.15` while keeping Next.js `16.2.9`, rejecting the audit tool's incompatible Next.js 9 downgrade.

## 1.6.0+20260613 - 2026-06-13

- Extracted shared Focus/session countdown, progress, and source-coverage behavior into a tested frontend runtime owner.
- Added pre-hydration preference bootstrap so theme, font, text size, and language attributes are correct before React mounts.
- Added an isolated production screenshot harness with automatic port allocation and explicit light/dark coverage for four primary routes.
- Added a dark-theme compatibility layer for legacy Tailwind slate/white utilities and visually verified the resulting release screenshots.
- Removed 40 unreferenced private compatibility wrappers from `research_service.py` and migrated the remaining owner tests away from facade-private calls.

## 1.5.0+20260613 - 2026-06-13

- Split work-task context/PDF/formal-document responsibilities and knowledge-intelligence entity-quality/commercial-text/report-metadata responsibilities into owned backend modules while retaining compatibility exports.
- Extracted inbox research form behavior and markdown archive parsing/comparison behavior into testable frontend model owners without changing route or presentation contracts.
- Added Vitest, Testing Library, jsdom, frontend model/component regression tests, and a unified frontend test step in `npm run check`.
- Added a day/night preference regression test covering system-theme resolution and DOM theme/font/text/language attributes.
- Upgraded Next.js and its ESLint config from `16.1.6` to `16.2.9` to address current framework security advisories.

## 1.4.0+20260613 - 2026-06-13

- Added a LangGraph `StateGraph` adapter behind the framework-neutral research workflow protocol.
- Preserved deterministic setup/generation dependency ports, callbacks, snapshots, and run-metric keys for direct parity measurement.
- Added explicit `deterministic` and `langgraph_shadow` engine selection while retaining deterministic production defaults.
- Added bounded LangGraph evaluation CLI selection without automatic production dual-runs or hidden model-cost multiplication.
- Pinned the LangGraph 1.x dependency line and documented the shadow promotion gates.

## 1.3.0+20260613 - 2026-06-13

- Added an executable 100-case research evaluation runner with bounded case selection and machine-readable JSON artifacts.
- Added case-level and aggregate scoring for citation support, answer-term coverage, behavior accuracy, latency, cost, and human-curated retrieval relevance.
- Kept retrieval metrics unavailable until expected source domains or URLs are curated, preventing keyword proxies from being reported as Recall, MRR, or NDCG.
- Added release-gate eligibility checks requiring a locked dataset, the complete case set, every required metric, and passing targets.
- Added an explicit live-provider cost confirmation before evaluation can use configured remote credentials.

## 1.2.1+20260613 - 2026-06-13

- Split the legacy LLM facade into protocol, mock provider, OpenAI adapter, fallback composition, and provider-router owner modules while retaining import compatibility.
- Persisted per-job research workflow metrics, node latency, token usage, and cost-ledger snapshots for successful and failed background jobs.
- Added a typed research-job metrics API plus Alembic and SQLite compatibility migrations.
- Added tracked-file secret scanning to CI and corrected the Focus E2E frontend health check to use the configured port `3010`.

## 1.2.0+20260613 - 2026-06-13

- Added a framework-neutral `LLMRunResult` contract for provider/model identity, token usage, cost estimates, attempts, response identifiers, finish reasons, and adapter metadata while preserving the existing JSON-string `run_prompt()` facade.
- Added the `langchain_openai` provider route with prompt-specific Pydantic structured output, `json_schema` as the primary method, and configurable `json_mode` fallback for compatible gateways.
- Added independent generation and strategy provider routing across `mock`, legacy `openai`, and `langchain_openai`, including fallback-key and mock-fallback composition.
- Added configurable model prices per one million input, cached-input, and output tokens instead of hard-coding time-sensitive vendor prices.
- Upgraded the research cost ledger to consume provider-reported usage and cached-token details, with estimated counting retained only for legacy compatibility services.
- Extended the LLM configuration and dry-run diagnostics with route, structured-output, usage, model, and pricing visibility.

## 1.1.1+20260612 - 2026-06-12

- Completed the research owner and dependency-seam migration for scope, entity policy, ranking, storage canonicalization, delivery, runtime dependencies, and report row quality while preserving the public research facade.
- Added the framework-neutral `ResearchWorkflowEngine` contract and kept the deterministic workflow as the default production implementation ahead of a future LangGraph shadow adapter.
- Added per-run `ResearchRunMetrics` and `CostLedger` snapshots for workflow stages, node latency, model-call status, estimated token volume, source counts, and section counts without logging prompt or source content.
- Added a versioned 100-case draft research evaluation dataset covering ten industry/guardrail suites and retrieval, citation, correctness, refusal, latency, and cost targets.
- Removed the real WeChat Mini Program AppID from the tracked worktree, stopped tracking private DevTools config, and retained explicit Git-history cleanup guidance for the remaining historical AppID exposure.

## 1.1.0+20260602 - 2026-06-02

- Expanded the solution architect workbench with capability-to-architecture mappings, ADR-style architecture decision records, and integration dependency diagnostics.
- Extended solution delivery markdown and the research report card to surface architecture decisions, source systems, API/data contracts, auth boundaries, deployment assumptions, owners, risks, and validation actions.
- Refactored the backend research and collector surfaces toward thinner workflow/application modules, including generation workflow, delivery materials, market intelligence, source enrichment, corrective expansion, and collector route domains.
- Split Research Center, Collector Ops, Topic Workspace, Knowledge Detail, Research Report Card, and Session Summary presentation/controller logic into smaller feature modules.
- Continued semantic theme-token migration across report cards, research panels, collector operations, knowledge detail, and session surfaces so light and dark modes share a stable design-system contract.
- Added bilingual README major-version highlights for GitHub and ModelScope distribution.

## 1.0.0+20260520 - 2026-05-20

- Added WeChat Favorites import for exported HTML/TXT, clipboard text, and `mp.weixin.qq.com` link lists, turning public-account favorites into normal homepage triage cards.
- Added backend parsing, URL normalization, deduplication, deferred processing, and import result reporting for WeChat Favorites batches.
- Switched WeChat Favorites URL imports onto the URL-first extraction route and added swipe/auto-advance triage for quick ignore/save handling in the homepage card deck.
- Added a latest-import review queue on the homepage with ready/processing/failed counts and item-id filtered feed refresh so WeChat Favorites batches become visible while background parsing is still running.
- Added batch retry for failed imported items, allowing the latest WeChat Favorites queue to reprocess failures without opening each item detail page.
- Made the latest WeChat Favorites queue shrink as users ignore or save cards, so processed items no longer return after the next automatic refresh.
- Added a WeChat Favorites preflight preview API and homepage preview button so users can verify recognized public-account links and text blocks before starting a batch import.
- Expanded WeChat Favorites parsing to keep mixed URL and text-block exports in one batch, and added multi-file `.url` / `.webloc` import support on the homepage panel.
- Hardened WeChat Favorites URL discovery for HTML entities, JSON-escaped links, and percent-encoded `.url` / browser shortcut exports while avoiding shortcut metadata as fake text cards.
- Kept the homepage refresh action scoped to the active WeChat Favorites review queue and added clearer all-failed parsing feedback with a compact queue progress bar.
- Persisted WeChat Favorites import batches in the backend, added batch list/detail APIs, and restored the latest unfinished homepage review queue after reload with done-count tracking.
- Added a solution architect workbench to delivery packs with customer scenarios, stakeholder question maps, decision criteria, validation actions, next-meeting agendas, markdown export, and research-report-card surfacing.
- Added the Alembic migration, SQLite compatibility coverage, API-level import/batch restoration tests, and release metadata for the 1.0.0 local-first baseline.

## 0.8.0+20260518 - 2026-05-18

- Added a solution-architecture readiness layer for generated solution delivery packs, scoring business alignment, architecture completeness, integration readiness, security/compliance readiness, and delivery feasibility.
- Added an architecture blueprint to the solution pack: business/role layer, application capability layer, model-data-integration layer, and security/deployment/operations layer, each with evidence and open questions.
- Extended solution delivery markdown exports and the research report card with architecture readiness, integration risks, non-functional requirements, stakeholder questions, and validation actions for solution architects and industry consultants.
- Repositioned README, whitepaper, launch kit, growth copy, screenshot coverage, and release history around solution architects, industry consultants, pre-sales teams, and advisory-grade delivery work.

## 0.7.0+20260518 - 2026-05-18

- Added a headless-source-first Focus collection path: starting or resuming Focus now brings up the source collector daemon first, with the WeChat PC agent kept as a supplementary URL harvester.
- Added collector run coverage metrics and source-level health diagnostics, including handled count, coverage rate, body success rate, poor/watch source counts, and per-source recommendations.
- Extended collector reports, Focus status, miniapp startup, and Collector Ops with source health visibility so operators can see which公众号 source is stale, failing, skipped, or under-covered instead of only seeing total coverage.
- Refreshed version metadata, GitHub-facing documentation, release screenshot coverage, product whitepaper, and commercial launch copy for the 0.7.0 reliability release.

## 0.6.11+20260514 - 2026-05-14

- Expanded GitHub-facing screenshot capture from the previous five-highlight set to release-grade coverage across the primary product surfaces: home, inbox, saved, focus, session summary, collector, settings, knowledge library, commercial hub, merge workflow, research center, topic workspace, compare workspace, experiment orchestration, and archive viewer.
- Added screenshot quality gates and a generated manifest so release screenshots fail fast on runtime overlays or suspiciously small/blank captures before they are committed.
- Added a feature screenshot coverage gallery and a release history / feature map that document historical major-version progress, the latest complete capability set, and industry-standard release checks for future iterations.
- Refreshed English and Chinese README product screenshots, current version metadata, and links to the full screenshot and capability-map docs.

## 0.6.10+20260514 - 2026-05-14

- Injected active experiment runtime config into report generation so query recovery and source-reranker policies can affect the actual research pipeline, not only retrieval APIs.
- Added runtime strategy diagnostics to research source diagnostics, including applied/fallback lanes, warnings, query-recovery state, and source-reranker state.
- Extended the experiment control panel with report-generation runtime config so operators can inspect query recovery and source reranker behavior before expanding rollout.

## 0.6.9+20260514 - 2026-05-14

- Added an effective runtime config resolver for query generation, section routing, retrieval search, source reranking, and all-lane consumers.
- Wired retrieval-index search and section-retrieval packs to consume the active experiment strategy layer for parent-block boost and official-source bias.
- Surfaced the effective retrieval config in the research-center experiment panel so operators can see the applied lanes, fallback lanes, and runtime warnings before rollout expansion.

## 0.6.8+20260514 - 2026-05-14

- Added a runtime strategy snapshot for promoted experiment policies, translating active query/routing/reranker lanes into explicit runtime config with provenance, gate metrics, and version-drift warnings.
- Added `/api/research/experiments/runtime-snapshot` so downstream strategy readers can consume the current default policy set without reparsing rollout manifests.
- Surfaced the runtime snapshot in the research-center experiment panel, including ready/degraded/empty status, lane config previews, and conflict or version warnings.

## 0.6.7+20260513 - 2026-05-13

- Added an active experiment policy registry that resolves promoted rollout manifests into one current strategy per lane and reports any remaining same-lane conflicts.
- Promotion now automatically supersedes older active rollout manifests in the same lane, revoking the previous policy and recording the superseded plan IDs in the activation payload.
- Extended the research-center experiment panel and repository screenshot set with the active policy registry so the GitHub README shows the new control-plane surface.

## 0.6.6+20260513 - 2026-05-13

- Added experiment rollout audit history: each gate evaluation is now appended to a bounded history instead of replacing the only decision record.
- Added rollout manifests for allowed strategies, including activation payload, baseline version, gate metrics, promotion note, and revocation state so rollout decisions are auditable before they touch runtime defaults.
- Extended the research-center orchestration panel with gate-history counts, rollout confirmation/revocation actions, manifest status, and promoted/revoked plan counters.

## 0.6.5+20260513 - 2026-05-13

- Upgraded the diagnostics control plane into a persistent experiment orchestration layer with configurable strategy plans, frozen cohorts, locked version baselines, and rollout gate decisions.
- Added backend persistence, Alembic migration, SQLite compatibility backfill, API endpoints, and service tests for experiment plan creation, cohort freeze, baseline lock, and gate evaluation.
- Added a research-center orchestration panel so operators can create plans, inspect frozen samples, lock baselines, and review allow/hold/block gate reasons beside existing diagnostics.

## 0.6.4+20260513 - 2026-05-13

- Added a research experiment control plane that compares query-recovery cohorts, follow-up routing cohorts, and same-sample reranker official-source Recall@5 so rollout choices are inspectable instead of implicit.
- Added follow-up delta offline evaluation for title handling, summary handling, impacted-section routing, and official-source support yield, with weak-sample surfacing for unfinished delta behavior.
- Added delivery export diagnostics history and adjacent-version comparisons across markdown archives, preserving quality snapshots, follow-up impact summaries, and export-change counts in one panel.
- Expanded retrieval-index runtime status into an optimization panel for remaining chunks, persisted-cache reuse, resume readiness, cache health, and recovery recommendations.

## 0.6.3+20260513 - 2026-05-13

- Extended the offline evaluation control plane with delivery-quality regressions: solution-delivery pass rate, project-proposal pass rate, and delivery self-review gain rate now sit beside retrieval, target-support, evidence-quota, and official-source recall metrics.
- Enriched weak-report regression entries with delivery-quality scores, worst delivery status, and missing proposal-review axes so operators can see which old reports still fail China-tech delivery expectations.
- Updated the research center regression panel and compare-snapshot compatibility parser so both live evaluations and frozen historical snapshots tolerate the expanded evaluation payload.

## 0.6.2+20260513 - 2026-05-13

- Added a China-tech delivery quality control plane for solution packs, feasibility-study exports, and project-proposal exports: outputs are scored against structure completeness, evidence grounding, execution readiness, and review governance.
- Added deterministic self-review and self-repair for weak delivery materials, automatically filling missing demand, architecture, safety/compliance, procurement/implementation, budget/performance, and risk/acceptance sections without upgrading weak evidence into strong claims.
- Surfaced solution-pack and project-proposal quality scores, self-review deltas, and delivery gaps in the research report card, while formal exported documents now append a delivery-quality audit trail before release.

## 0.6.1+20260510 - 2026-05-10

- Added quality-triggered public-source expansion for research reports and advisory delivery materials: when self-evaluation stays at watch/fail quality, the pipeline expands beyond configured source settings into public procurement, public resource, official, disclosure, open web, and public WeChat channels, merges new evidence, rebuilds material packs, and re-evaluates the result.
- Surfaced quality-expansion diagnostics in the research report card, including rounds, added public source count, self-evaluation score movement, expansion notes, and representative public search queries.

## 0.6.0+20260508 - 2026-05-08

- Upgraded research reranking from the local heuristic path to a lazy SentenceTransformers CrossEncoder adapter with backend diagnostics and local fallback, and added offline reranker official-source Recall@5.
- Hardened the CrossEncoder adapter fallback path so missing SentenceTransformers dependencies or malformed model score counts keep all candidate sources via local reranking instead of silently truncating results.
- Cleaned WeChat local homepage/OCR headers so account name + timestamp strings no longer become feed card titles after switching into Focus mode.
- Added retrieval-index status reporting and research-center visualization for resumable rebuild progress, persisted chunk counts, parent-block links, and orphan child chunks while preserving official-source priority under parent-block routing boost.
- Added Watchlist run history, default failed-run retry, notification summaries, SQLite/Alembic persistence, API client types, and Markdown digest export in the research center.
- Added advisory-grade delivery artifacts in the solution delivery pack: client brief, bidding prep memo, and execution materials, all carrying source policy and review checklist metadata.
- Tightened semiconductor entity cleanup so product/project strings like "12英寸CIS集成" and "300毫米硅片全自动智能" trim back to real organization candidates instead of leaking as ranked entities.

## 0.5.2+20260507 - 2026-05-07

- Closed the 0.5.0.x retrieval substrate follow-up with schema v2 chunks, sentence-window splitting, stable chunk IDs, report/section parent links, richer region / industry / perspective metadata, and broader retrieval-index search filters.
- Added the first 0.5.1.x reranker and evaluation follow-up: feature-flagged local cross-encoder-style top-k reranking diagnostics plus offline official-source Recall@5 and unsupported-target-rate metrics.
- Added Watchlist operations health summary for the continuous research workspace, including due / overdue / stale / failed-topic counts, recommendations, API client types, and research-center UI surfacing.
- Verified with full backend tests, frontend lint, and production build before release tagging.

## 0.5.1+20260502 - 2026-05-02

- Added CRAG-style retrieval correction profile that grades each source as accepted / ambiguous / rejected, generates corrective query plans, and renders compressed retrieval context for prompt injection (`research_rag_quality_service`).
- Added a generation grounding review pass that classifies report claims as supported vs unsupported against the source corpus and emits `generation_grounding_score`, `response_quality_score`, and `generation_review_notes`.
- Added a research report self-evaluation profile (`research_report_evaluation_service`) covering faithfulness, answer relevancy, context coverage, citation quality, and entity recall, with per-metric evidence and corrective query suggestions surfaced in the report card so weak reports are visible before export.
- Surfaced supported claims, unsupported claims, and per-metric evidence in the API client types and report card UI.
- Cross-encoder reranker model integration and offline ms-marco evaluation remain the next 0.5.1.x step.

## 0.5.0+20260502 - 2026-05-02

- Indexed watchlists, watchlist change events, Commercial Hub signals, account context, and archive recap diagnostics as first-class retrieval documents on the unified retrieval substrate (rolls up the in-tree 0.5.0+20260429 draft).
- Added `knowledge_cleaning_service` for low-signal pruning, row deduplication, and title normalization across knowledge intake (`item_processor`, `knowledge_service`), intelligence (`knowledge_intelligence_service`), and retrieval (`knowledge_retrieval_service`) surfaces.
- Tightened entity quality pipeline: candidate procurement and organization extraction, role-aware deduplication, and review-queue hand-off so noisy or ambiguous entities no longer leak into account, competitor, and partner rankings.
- Refreshed knowledge UI cards (detail, account workspace, commercial hub) to render cleaned content and surface low-signal placeholders instead of empty rows.
- Parent-child chunking, sentence-window chunks, stable chunk IDs across re-index, and broader API filters remain part of the 0.5.0.x follow-up step.

## 0.4.3+20260502 - 2026-05-02

- Added structured follow-up section impact diagnostics (`ResearchFollowupSectionImpactOut`) so every follow-up run lists impacted chapters, reasons, retrieval support score, official-source hit count, and next action instead of generic notes.
- Distinguished follow-up title and summary resolution (`kept baseline` vs `corrected`) and propagated the result through workspace store, archive cards, topic timeline, and compare/export metadata.
- Fed impacted-section hints into report generation prompt context so follow-up mode prioritizes affected chapters rather than flattening the whole report.
- Surfaced impacted sections and follow-up resolution in the research center, topic workspace, archive viewer, compare matrix, and report card.

## Operations and platform - 2026-05-02

- Added LLM provider quota fallback (`openai_fallback_api_key`, `strategy_openai_fallback_api_key`) and a tolerant JSON parser that accepts markdown-fenced and trailing-comma payloads so model responses with near-valid JSON no longer fail validation.
- Added a summary boilerplate stripper that removes WeChat collector article-metric headers (`本文字数 / 阅读时长 ...`) before prompt rendering, keeping summaries focused on substantive content.
- Allowed `finish_session` to regenerate summary text on already-finished sessions instead of raising, so users can re-trigger summary generation if the original finish call missed language settings.
- Added two end-to-end probes (`scripts/wechat_pc_right_click_probe.py`, `scripts/wechat_pc_open_in_browser_probe.py`) for the WeChat PC article window so the collector reliability roadmap item can be validated outside the main daemon.

## 0.4.2+20260424 - 2026-04-24

- Added a scenario/customer/vertical-scene review loop in the research workspace with direct refresh of market intelligence and solution delivery packs.
- Added standalone Markdown exports for the three-year market-intelligence pack and the solution-delivery/PPT-outline pack.
- Updated formal feasibility-study and project-proposal exports to rebuild scenario intelligence from the current delivery supplement instead of stale report-side packs.
- Preserved labeled metadata rows in formal documents so target customer, scenario, vertical scene, source count, and evidence notes remain readable in exports.
- Replaced the remote `next/font/google` Geist dependency with local fallback font stacks so `next build` succeeds in offline or restricted-network environments.
- Refreshed the GitHub-facing README, Chinese README, repository about copy, homepage link, topics, and launch/growth copy to better position the project for open-source discovery.
- Added real product screenshots and a reusable `npm run repo:screenshots` capture script for GitHub-facing documentation assets.
- Brought section-level retrieval packs into generation-time prompt context and delivery-time report enrichment so report chapters use ranked evidence instead of diagnostics-only display.
- Surfaced follow-up routing diagnostics through topic side-by-side compare, archive compare/export metadata, and delivery digests so title/summary handling and impacted sections stay visible after archival.

## 0.4.1+20260423 - 2026-04-23

- Added a three-year public tender and product intelligence pack to research reports, covering tender/project details, product lists, technical parameters, source queries, evidence gaps, and Markdown export content.
- Added solution delivery package generation for concrete scenarios such as ecommerce digital humans, cultural-tourism AIGC platforms, AI marketing platforms, and government AI solutions.
- Added feasibility-study, project-proposal, and client-facing PPT outline structures with review checklists before final document refinement.
- Surfaced tender/product/technical-parameter intelligence and solution delivery outlines in the research report card.
- Extended formal feasibility-study and project-proposal exports with tender intelligence, product lists, and technical-parameter evidence.

## 0.4.0+20260423 - 2026-04-23

- Added chapter-level retrieval packs that convert methodology axes into section-specific retrieval targets and route research retrieval index hits back to report sections.
- Added golden report evaluation with fixed government-cloud, compute/LLM, and weak generic cases measuring professional score, intelligence value, target-account support, and section evidence quota pass rate.
- Added persistent research retrieval index storage with SQLite chunk records, rebuild checkpoints, resumable batch rebuild, incremental upsert, persistent load, and search endpoints.
- Added API and frontend client types for section retrieval packs, golden evaluation, persistent retrieval-index rebuild, and persistent retrieval-index search.
- Extended SQLite compatibility backfill and tests for the new retrieval-index tables.

## 0.3.1+20260423 - 2026-04-23

- Added a report quality profile focused on professional rigor, intelligence value, actionability, and evidence strength.
- Added industry methodology playbooks for government cloud, compute/LLM infrastructure, AI applications, and generic B2B solution research.
- Added section-level evidence packs that expose support score, official-evidence count, quota gaps, risks, and next verification actions.
- Surfaced the quality profile in API types and the report card UI so report quality gaps are visible before export or follow-up.
- Tightened report and outline prompts around methodology gates, intelligence value, evidence anchors, and actionability checks.
- Documented the next version iteration plan with date-stamped versioning rules.

## 0.3.0+20260423 - 2026-04-23

- Stabilized the compare/export delivery chain with version diff recap, evidence appendix, Markdown/PDF/Exec Brief exports, archive recap exports, and section-level diagnostics.
- Added persistent `compare_snapshot.metadata_payload` with SQLite compatibility backfill, frozen offline-evaluation snapshots, and legacy snapshot backfill disclosure in the compare UI and exports.
- Added offline research evaluation metrics for retrieval hit rate, target-account support rate, and section evidence quota pass rate.
- Strengthened research quality gates around canonical organization linking, official-source support, guarded backlog handling, and low-quality report rewrite/backfill.
- Added the first RAG quality-engineering baseline: hybrid retrieval tests, knowledge retrieval previews, and report-level evidence chunk retrieval.
- Fixed the antifomo Web port baseline to `3010` and refreshed the local start/stop scripts around the dedicated port.
