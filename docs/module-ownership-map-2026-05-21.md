# Module Ownership Map

Updated: 2026-06-13

This map records the current ownership boundaries after the first modular refactor slices. It is intended to keep future development from drifting back into broad orchestration files.

## Backend

Allowed dependency direction:

- `api` may depend on `services`, `schemas`, `models`, and `core`.
- Orchestration services may depend on cohesive domain services.
- Domain-style service submodules should not depend on API routers or their parent orchestration service.
- Delivery submodules may depend on schemas and shared text utilities, but not on `research_solution_intelligence_service.py`.

Current owners:

| Area | Owner module | Responsibility |
| --- | --- | --- |
| WeChat Favorites import parsing | `backend/app/services/collector_imports/wechat_favorites.py` | WeChat export decoding, URL/text candidate extraction, import batch assembly. |
| Collector browser/plugin/URL ingest API | `backend/app/api/collector_ingest.py` | Browser extraction ingest, browser batch ingest, plugin body ingest, direct URL ingest, and shared item-ingest attempt handling. |
| Collector source/feed API | `backend/app/api/collector_sources.py` | Collector source CRUD/import, RSS feed source registration, feed listing, and RSS pull endpoints. |
| Collector external ingest API | `backend/app/api/collector_external_ingest.py` | Newsletter, uploaded document, and YouTube transcript ingest endpoints. |
| Collector OCR helpers | `backend/app/api/collector_ocr.py` | OCR preview quality gates, crop retry profiles, and OCR preview retry orchestration. |
| Collector OCR API routes | `backend/app/api/collector_ocr_routes.py` | OCR image ingest and OCR preview HTTP entrypoints. |
| Collector operations API | `backend/app/api/collector_operations.py` | Pending recovery, failed queue, retry, daily summary, ingest attempts, collector status, and collector daemon endpoints. |
| Collector WeChat agent API | `backend/app/api/collector_wechat_agent.py` | WeChat agent status/config/health/self-heal/preview/start-stop/run/batch/dedup endpoints. |
| Collector WeChat Favorites API | `backend/app/api/collector_wechat_favorites.py` | WeChat Favorites preview, import batch listing/detail/restore response mapping, and import endpoints. |
| Collector URL resolve API | `backend/app/api/collector_url_resolve.py` | WeChat article URL resolution from preview title/body evidence. |
| Collector ops API serialization | `backend/app/api/collector_ops_serializers.py` | Collector daemon and WeChat agent status/command/route-quality response mapping for the ops API. |
| Collector API URL utilities | `backend/app/api/collector_url_utils.py` | Shared collector API URL validation, source URL normalization, and text cleanup helpers. |
| Collector persistence facade | `backend/app/services/collector_multiformat_service.py` | Shared collector persistence, batch compatibility wrappers, non-WeChat collector ingest flows. |
| Market intelligence | `backend/app/services/delivery/market_intelligence.py` | Public-source qualification, three-year tender extraction, product/technical parameter catalogs, market markdown. |
| Solution architecture | `backend/app/services/delivery/solution_architecture.py` | Architecture readiness, blueprint layers, stakeholder maps, capability matrix, ADRs, integration dependencies. |
| Delivery materials | `backend/app/services/delivery/solution_materials.py` | Feasibility/proposal/PPT outlines, advisory artifacts, solution delivery markdown serialization. |
| Solution delivery orchestration | `backend/app/services/research_solution_intelligence_service.py` | Scenario resolution, evidence policy, pack assembly, quality review, architecture enrichment, export assignment. |
| Research report markdown | `backend/app/services/research/report_markdown.py` | Full research report markdown serialization and report filename derivation. |
| Research report storage mapping | `backend/app/services/research/report_storage.py` | Stored report section aliases, stored-report-to-result mapping, and persisted source reconstruction. |
| Research source documents | `backend/app/services/research/source_documents.py` | Source document DTO, source text noise cleanup, source-document text assembly, and conversion to research source outputs. |
| Research archive context | `backend/app/services/research/archive_context.py` | Historical research/knowledge prompt rendering, archive query expansion, and archive scope-hint merge policy. |
| Research archive loader | `backend/app/services/research/archive_loader.py` | Historical research/knowledge candidate loading, stored report payload parsing, archive item construction, and retrieval-match materialization. |
| Research runtime config | `backend/app/services/research/runtime_config.py` | Research mode runtime limits, query recovery overrides, and generation/search timeout budget calculation. |
| Research source collection | `backend/app/services/research/source_collection.py` | Adapter/public-web hit collection, initial hit balancing, and initial source extraction/filtering. |
| Research company/source enrichment | `backend/app/services/research/company_source_enrichment.py` | Company profile/contact search planning, official source fallback, enriched-source merge/refine, and source-intelligence refresh. |
| Research evidence expansion | `backend/app/services/research/evidence_expansion.py` | General weak-evidence detection, expanded query execution, expanded-source merge/refine, and source-intelligence refresh. |
| Research corrective expansion | `backend/app/services/research/corrective_expansion.py` | Low-quality retrieval detection, corrective query planning, corrective source collection, scope refresh, and retrieval-correction profile output. |
| Research tender-detail enrichment | `backend/app/services/research/tender_detail_enrichment.py` | Confirmed tender scoring, tender detail query planning, tender detail source collection, and post-tender source-intelligence refresh. |
| Research candidate-profile enrichment | `backend/app/services/research/candidate_profile_enrichment.py` | Candidate company profile/contact/team search, profile-source merge, reranking refresh, and candidate diagnostics counters. |
| Research source intelligence | `backend/app/services/research/source_intelligence.py` | Source-derived business intelligence rows for accounts, teams, budgets, tenders, competitors, partners, methodology, and outlook dimensions. |
| Research source diagnostics | `backend/app/services/research/source_diagnostics.py` | Source coverage counters, evidence mode, retrieval-quality bands, normalized-entity coverage, and pipeline diagnostics construction. |
| Research source query plans | `backend/app/services/research/source_query_plans.py` | Base, scoped official, corrective, expanded, and company profile/contact/team query plan construction. |
| Research source scoping policy | `backend/app/services/research/source_scope_policy.py` | Source theme/scope scoring, company-anchor filtering, recency filtering, report-source refinement, and region-conflict signatures. |
| Research scope terms | `backend/app/services/research/scope_terms.py` | Keyword/focus cleanup, explicit exclusions, topic/company anchors, resolved company terms, and theme-term construction. |
| Research ranking/source utility | `backend/app/services/research/ranking_source_utility.py` | Source-derived organization rows, key people, department, and public contact row extraction utilities. |
| Research report field sanitization | `backend/app/services/research/report_field_sanitization.py` | Report row validity checks, entity row normalization, generic row filtering, and field-level canonical deduplication. |
| Research entity graph builder | `backend/app/services/research/entity_graph_builder.py` | Normalized entity graph construction, role inference, alias aggregation, source-tier counts, and graph lookup support. |
| Research quality expansion | `backend/app/services/research/quality_expansion.py` | Self-evaluation-triggered public-source expansion, quality expansion query planning, source merge/rebuild, and post-expansion evaluation. |
| Research generation execution | `backend/app/services/research/generation_execution.py` | Partial outline generation, draft snapshot, section retrieval prompt context, final LLM prompt execution, parsing, intelligence merge, and refinement. |
| Research generation setup | `backend/app/services/research/generation_setup.py` | Pre-generation environment setup: settings/LLM/runtime, follow-up scope diagnostics, strategy scope planning, source settings, and archive context assembly. |
| Research generation workflow | `backend/app/services/research/generation_workflow.py` | Research generation application workflow spine: planning, source collection, enrichment, generation execution, ranking, assembly, quality review, and snapshot return using stage-scoped compatibility dependency ports. |
| Research workflow engine | `backend/app/services/research/workflow_engine.py` | Framework-neutral workflow protocol, deterministic engine implementation, callback preservation, and run-metrics lifecycle. |
| Research LangGraph workflow engine | `backend/app/services/research/langgraph_workflow_engine.py` | Production `StateGraph` adapter over the same framework-neutral setup/generation ports, with deterministic rollback kept outside the graph implementation. |
| Research workflow parity | `backend/app/services/research/workflow_parity.py` | Locked-dataset offline orchestration equivalence gate covering reports, callbacks, snapshots, metrics, and all 100 cases without network or model cost. |
| Research run metrics | `backend/app/services/research/run_metrics.py` | Per-run node/stage timing, counters, gauges, model-call token estimates, and cost-ledger aggregation without prompt/source-content logging. |
| Research evaluation dataset | `backend/app/services/research/evaluation_dataset.py`, `backend/evaluation/research_golden_v1.json` | Versioned and locked 100-case evaluation manifest, suite expansion, review metadata, lock digest, expected behavior, first-party source expectations, and retrieval/quality/cost targets. |
| Research evaluation review | `backend/app/services/research/evaluation_review.py` | Independent review packet construction, immutable case-context verification, reviewer separation, approval completeness, attestation, and review content digest validation. |
| Research evaluation budget | `backend/app/services/research/evaluation_budget.py` | Live-provider batch planning, target cost ceilings, approved-budget checks, observed cost accounting, and stop conditions for unpriced or over-budget runs. |
| Research evaluation scope feedback | `backend/evaluation/research_scope_feedback_resolution_v1_2.json`, `scripts/apply_research_evaluation_scope_feedback.py` | Auditable mapping from reviewer comments to region/entity scope changes, stale-digest protection, and repeatable application without changing approved answer/source/behavior fields. |
| Research generation facade | `backend/app/services/research_service.py` | Public research-generation compatibility entrypoint, setup binding, workflow dependency wiring, and legacy monkeypatch wrappers while residual policy wrappers are retired. |
| Research strategy refinement | `backend/app/services/research/strategy_refinement.py` | Topic-specific report overrides, strategy scope LLM planning, and post-generation strategy LLM refinement. |
| Research stored-report rewrite | `backend/app/services/research/stored_report_rewrite.py` | Stored report rewrite orchestration, guarded backlog report assembly, guard assessment, target support checks, low-signal source checks, guarded diagnostics, and guarded title generation. |
| Research report readiness | `backend/app/services/research/report_readiness.py` | Report readiness scoring, resolved readiness fallback, and low-signal execution guard policy. |
| Research action cards | `backend/app/services/research/action_cards.py` | Research action-card construction, action evidence formatting, buyer/partner/project timing cards, and minimum-input gates. |
| Research delivery enrichment | `backend/app/services/research/delivery_enrichment.py` | Report readiness, commercial summary, appendix/review queue refresh, runtime section packs, market/delivery pack refresh, and readiness guardrails. |
| Research delivery materials | `backend/app/services/research/delivery_materials.py` | Commercial summary, technical appendix, scenario comparison, and review queue construction for research reports. |
| Research entity ranking | `backend/app/services/research/entity_ranking.py` | Target account, competitor, and ecosystem-partner ranking set construction, entity ranking heuristics, candidate-profile support scoring, and candidate-profile promotion. |
| Research generation artifacts | `backend/app/services/research/generation_artifacts.py` | Outline fallback generation and partial report response materialization before final synthesis. |
| Research section retrieval | `backend/app/services/research_section_retrieval_service.py` | Section retrieval targets, section evidence packs, section-pack prompt rendering, and runtime pack attachment. |
| Research retrieval orchestration | `backend/app/services/research/retrieval_orchestration.py` | Runtime section retrieval index orchestration and generation-time section/follow-up context injection. |
| Research final report assembly | `backend/app/services/research/report_assembly.py` | Final research-report DTO assembly from parsed result, ranked entities, diagnostics, and source outputs. |
| Research report persistence | `backend/app/services/research/report_persistence.py` | Saved research report lookup and knowledge-entry upsert persistence. |
| Research section quality | `backend/app/services/research/section_quality.py` | Section evidence links, evidence quotas, confidence tone, insufficiency reasons, and verification-step scoring. |
| Research follow-up diagnostics | `backend/app/services/research/followup_diagnostics.py` | Follow-up context shaping, scope-hint rebuild, query decomposition, impacted-section scoring, and prompt-context rendering. |
| Research stored entity canonicalization | `backend/app/services/research/stored_entity_canonicalization.py` | Stored-report entity canonical names, ranked-entity deduplication, persisted result canonicalization, and candidate profile company-name cleanup. |
| Research public web search | `backend/app/services/research/web_search.py` | Public web search hit model, DuckDuckGo/Bing HTML parsing, SSL fallback URL opening, and cross-engine deduplication. |

Fitness checks:

- `backend/tests/test_architecture_boundaries.py` prevents delivery modules from importing the solution orchestration service or API layer.
- The same test keeps `research_solution_intelligence_service.py` under a thin-orchestrator line-count ceiling and verifies that markdown/material/tender builders stay delegated.

Current backend hotspots still requiring future slices:

| File | Approx. size | Risk |
| --- | ---: | --- |
| `backend/app/services/research_service.py` | 3,739 lines | The public facade retains compatibility aliases and workflow dependency wiring after 40 unreferenced private wrappers were removed. New orchestration implementations must enter through `ResearchWorkflowEngine`; remaining facade size is compatibility risk, not an invitation for helper-level splitting. |
| `backend/app/services/research/generation_workflow.py` | 804 lines | Workflow spine is isolated and its public dependency surface is grouped into progress/source-collection/scope/enrichment/generation/ranking/assembly/quality ports; remaining risk is internal workflow length rather than a flat injection list. |
| `backend/app/services/knowledge_intelligence_service.py` | 1,457 lines | Compatibility/application service after entity-quality, commercial-text, and report-metadata extraction; future changes should enter the owned package first. |
| `backend/app/services/work_task_service.py` | 1,101 lines | Task orchestration and compatibility exports after context, PDF, and formal-document extraction; future export behavior should enter `work_tasks/` owners. |
| `backend/app/schemas/research.py` | 1,865 lines | DTO growth is concentrated; future schema versioning or feature splits may be needed. |

## Frontend

Allowed dependency direction:

- `app` route files should remain route shells and delegate to feature components.
- `components/layout` may depend on preferences and reusable UI primitives, but should not own feature state.
- `src/lib/api.ts` remains the compatibility facade while feature clients are gradually extracted under `src/lib/api/`.
- Shared visual surfaces should consume semantic theme tokens rather than hard-coded light palette classes.

Current owners:

| Area | Owner module | Responsibility |
| --- | --- | --- |
| API transport | `src/lib/api/client.ts` | Runtime API base resolution, JSON fetch wrapper, API base override key. |
| Items API client | `src/lib/api/items.ts` | Item list/detail/create, preferences, diagnostics, feedback, reprocess, interpretation, and add-to-knowledge calls. |
| Research API client | `src/lib/api/research.ts` | Research reports/jobs/conversations, workspace, evaluation, retrieval, watchlists, delivery pack, tracking topic, and action-plan calls. |
| Knowledge API client | `src/lib/api/knowledge.ts` | Knowledge entries, dashboard, account intelligence, opportunities, markdown, review queue, merge preview, and rule calls. |
| Collector API client | `src/lib/api/collector.ts` | Collector daemon, WeChat agent, failed queue, source/feed management, external ingest, and WeChat Favorites import calls. |
| Sessions API client | `src/lib/api/sessions.ts` | Focus sessions, session artifacts, todo calendar preview/import, and focus-assistant plan/action calls. |
| Tasks API client | `src/lib/api/tasks.ts` | WorkBuddy health/webhook bridge and async task create/detail calls. |
| System/settings API client | `src/lib/api/system.ts` | API health, LLM configuration, and LLM dry-run calls. |
| API DTO contracts | `src/lib/api/types.ts`, `src/lib/api/type-contracts/*.ts` | Stable DTO re-export entry plus feature-domain request/response contracts for items, research, knowledge, collector, sessions, tasks, and system settings. |
| Research report DTO contracts | `src/lib/api/type-contracts/research-report.ts` | Research report, source diagnostics, entity evidence, readiness, quality profile, follow-up diagnostics, jobs, conversations, daily brief, source settings, action cards, and save responses. |
| Research delivery DTO contracts | `src/lib/api/type-contracts/research-delivery.ts` | Market intelligence, tender/product requirements, solution delivery pack, delivery quality, architecture readiness, and architect workbench contracts. |
| Research workspace DTO contracts | `src/lib/api/type-contracts/research-workspace.ts` | Tracking topics, report versions, timelines, compare snapshots, markdown archives, entity details, workspace, and topic refresh contracts. |
| Research watchlist DTO contracts | `src/lib/api/type-contracts/research-watchlists.ts` | Watchlists, watchlist refreshes, run-due responses, run history, digest exports, ops summaries, and automation status contracts. |
| Research evaluation DTO contracts | `src/lib/api/type-contracts/research-evaluation.ts` | Low-quality review queue, offline evaluation, follow-up delta evaluation, delivery export diagnostics, and golden evaluation contracts. |
| Research experiment DTO contracts | `src/lib/api/type-contracts/research-experiments.ts` | Experiment lanes, control plane, gate configs/history, rollout manifests, active policies, runtime snapshots, effective runtime config, and orchestration plans. |
| Research retrieval DTO contracts | `src/lib/api/type-contracts/research-retrieval.ts` | Section evidence packs, section retrieval packs, retrieval index rebuild/status, and retrieval search result contracts. |
| API compatibility facade | `src/lib/api.ts` | Feature-client re-exports and the historical `toFeedCardLabel` helper during migration. |
| App preferences | `src/components/settings/app-preferences-provider.tsx` | Theme/font/language preference state and DOM data attributes. |
| Preference bootstrap | `src/lib/preference-bootstrap.ts` | Pre-hydration validation and application of persisted theme, font, text-size, language, and mode attributes. |
| Focus runtime model | `src/lib/focus-runtime-model.ts` | Shared countdown formatting, session restoration, progress calculations, batch snapshot detection, and source-coverage semantics for Focus and session summary. |
| Release screenshot harness | `scripts/capture_release_screenshots.sh`, `scripts/capture_repo_screenshots.mjs` | Isolated production build/server lifecycle, free-port allocation, light/dark route matrix, theme assertions, overlay checks, and screenshot manifest generation. |
| Theme tokens | `src/app/globals.css` | Semantic surface/text/border/accent tokens, shared primitive classes, and the restored translucent light/dark visual baseline aligned with the earlier `v0.8.0+20260518` UI direction. |
| Layout shell | `src/components/layout/main-nav.tsx`, `src/components/layout/page-shell.tsx` | Shared navigation and page headings using semantic tokens. |
| Common settings | `src/components/settings/common-settings-panel.tsx` | Preference controls using tokenized shared primitives. |
| Knowledge detail card | `src/components/knowledge/knowledge-detail-card.tsx` | Knowledge entry detail/edit presentation, embedded research report diagnostics, commercial intelligence, action cards, review queue actions, related entries, and tokenized knowledge-detail surfaces. |
| Session summary panel | `src/components/session/session-summary-panel.tsx` | Focus-session summary dashboard, collector batch snapshot, latest item digest, research recommendations, action-plan export, watchlist priority cards, and tokenized summary surfaces. |
| Research report delivery section | `src/components/inbox/research-report-delivery-section.tsx` | Solution delivery pack, market intelligence, architecture readiness, and advisory artifact rendering. |
| Research report source diagnostics section | `src/components/inbox/research-report-sources-diagnostics-section.tsx` | Query plan, source routing, diagnostic gates, entity coverage, and grouped source evidence rendering. |
| Research report insight sections | `src/components/inbox/research-report-insights-section.tsx`, `src/components/inbox/research-report-review-queue-section.tsx`, `src/components/inbox/research-report-appendix-section.tsx` | Main report insights, review queue, and technical appendix rendering. |
| Research report readiness and strategic sections | `src/components/inbox/research-report-readiness-section.tsx`, `src/components/inbox/research-report-strategic-section.tsx`, `src/components/inbox/research-report-source-list-section.tsx` | Readiness/playbook, strategic ranked panels, peer movement, highlight panels, and final source-list rendering. |
| Research report card view model | `src/components/inbox/research-report-card-view-model.ts` | Quality/readiness/profile summary calculations, source grouping, diagnostics meta, delivery/readiness metadata, retrieval routing cards, and report-surface copy derivation. |
| Inbox research form model | `src/components/inbox/inbox-form-model.ts` | Research mode budgets, keyword grouping, delivery supplement defaults, source-tier classification, progress-stage mapping, and stable UI labels. |
| Research center markdown archives section | `src/components/research/research-center-markdown-archives-section.tsx` | Research center archive filtering controls, archive cards, delivery digest chips, archive action links, and tokenized archive status surfaces. |
| Research center experiment/control section | `src/components/research/research-center-experiment-control-section.tsx` | Offline quality evaluation, retrieval-index rebuild controls, experiment control plane, rollout orchestration, runtime strategy snapshots, and delivery export diagnostics. |
| Research center watchlist section | `src/components/research/research-center-watchlist-section.tsx` | Watchlist digest export, due-run action, automation health, run history, copyable ops commands, per-watchlist schedule/status/refresh controls, and tokenized operation surfaces. |
| Research center low-quality review section | `src/components/research/research-center-low-quality-review-section.tsx` | Low-quality research audit queue cards, rewrite action, accept/revert controls, rewrite snapshot preview, and tokenized audit status surfaces. |
| Research center results section | `src/components/research/research-center-results-section.tsx` | Research result workspace header, loading/empty/error states, report/action cards, source diagnostics chips, action-card previews, ranked entity previews, and tokenized report/result card surfaces. |
| Research center source settings section | `src/components/research/research-center-source-settings-section.tsx` | Public research source toggles, enabled-source summary, connector authorization status, save/error presentation, and tokenized source status surfaces. |
| Research center sidebar controls | `src/components/research/research-center-sidebar-controls.tsx` | Daily Brief rendering, keyword search, focus toggle, retrieval lens, perspective, facet selects, filtered-count controls, and tokenized sidebar surfaces. |
| Research center workspace sections | `src/components/research/research-center-workspace-sections.tsx` | Saved compare snapshots, saved views, tracking topic cards, topic refresh/apply/watchlist actions, topic version history chips, and tokenized workspace surfaces. |
| Research center controller | `src/components/research/use-research-center-controller.ts` | Research center aggregation hook for filter state, cross-section href builders, controller composition, and section-scoped prop bundles. |
| Research center view model | `src/components/research/use-research-center-view-model.ts` | Research Center pure derived state: sorted/visible items, facet options, filter meta, perspective meta, overview stats, retrieval-lens counts, and active filter labels. |
| Research center source settings controller | `src/components/research/use-research-center-source-settings-controller.ts` | Public research source settings loading, default fallback, save state, source toggle persistence, and connector status error handling. |
| Research center Daily Brief controller | `src/components/research/use-research-center-daily-brief-controller.ts` | Daily Brief loading, refresh action, refresh/loading flags, and brief error state. |
| Research center cards controller | `src/components/research/use-research-center-cards-controller.ts` | Research report/action-card knowledge entry loading, focus/query scoped refresh, normalized card state, loading state, and load errors. |
| Research center low-quality controller | `src/components/research/use-research-center-low-quality-controller.ts` | Low-quality review queue loading, rewrite/accept/revert actions, queue refresh, action state, messages, and dependent evaluation/report refresh callbacks. |
| Research center experiment controller | `src/components/research/use-research-center-experiment-controller.ts` | Offline evaluation, control-plane diagnostics, runtime strategy snapshots, follow-up and delivery diagnostics, experiment plans/actions, and retrieval-index status/rebuild actions. |
| Research center archive controller | `src/components/research/use-research-center-archive-controller.ts` | Markdown archive filter/sort state, visible archive derivation, delivery digest scoring, archive downloads, and archive deletion actions. |
| Research center workspace controller | `src/components/research/use-research-center-workspace-controller.ts` | Workspace loading, saved views, tracking topics, compare snapshots, topic refresh, topic apply, and saved workspace action state. |
| Research center watchlist controller | `src/components/research/use-research-center-watchlist-controller.ts` | Watchlist loading, automation status, ops summaries, digest export, due-run orchestration, run history, schedule/status updates, refresh actions, and copyable ops commands. |
| Research center derived data utilities | `src/components/research/research-center-utils.ts` | Research center entry normalization, preview extraction, ranked/evidence metadata, semantic label/tone helpers, watchlist formatting, and route builders. |
| Research compare matrix | `src/components/research/research-compare-matrix.tsx` | Saved/live compare matrix presentation, snapshot diff panels, section diagnostics, quality review cards, entity evidence rows, filter controls, and tokenized compare surfaces. |
| Research topic workspace controller | `src/components/research/use-research-topic-workspace-controller.ts` | Topic detail loading, version/timeline/offline-evaluation loading, compare selection state, entity selection state, derived diff/ranking/source panels, action-card regeneration, recap export, PDF export, exec brief export, and archive-save workflows. |
| Research topic workspace utilities | `src/components/research/research-topic-workspace-utils.ts` | Topic version diff rows, semantic quality/timeline/entity tone helpers, ranked entity fallback, score panels, evidence links, and source contribution calculations. |
| Research topic entity workspace section | `src/components/research/research-topic-entity-workspace-section.tsx` | Normalized entity groups, entity selection pills, alias/source counts, and selected-entity evidence links. |
| Research topic version compare section | `src/components/research/research-topic-version-compare-section.tsx` | Version selector presentation, side-by-side report comparison, follow-up impact panels, diff highlights, field-diff rows, score panels, source contribution rendering, and tokenized topic-compare surfaces. |
| Research topic timeline section | `src/components/research/research-topic-timeline-section.tsx` | Topic version/snapshot/archive timeline cards, timeline stats, baseline/current selection actions, archive deep links, and linked snapshot/report actions. |
| Research console panel | `src/components/research/research-console-panel.tsx` | Research conversation loading, topic-scoped message thread rendering, suggested follow-up actions, timeline display, and tokenized console surfaces. |
| Research markdown archive viewer | `src/components/research/research-markdown-archive-viewer.tsx` | Markdown archive preview, archive comparison, follow-up/quality/section diagnostics, export/save actions, and tokenized archive preview surfaces. |
| Research markdown archive model | `src/components/research/research-markdown-archive-model.ts` | Markdown block parsing, archive section canonicalization, diff comparison, archive navigation links, status labels, and non-React archive behavior. |
| Research archive section link popover | `src/components/research/research-archive-section-link-popover.tsx` | Archive compare section deep-link loading, copy/open actions, fallback summary links, and tokenized popover states. |
| Collector ops panel shell | `src/components/settings/collector-ops-panel.tsx` | Collector settings composition, preference lookup, and section wiring. |
| Collector ops copy map | `src/components/settings/collector-ops-panel-copy.ts` | Collector operations localization map and stable `localText` lookup. |
| Collector ops panel controller | `src/components/settings/use-collector-ops-panel-controller.ts` | Collector status aggregation, failed queue loading, batch polling, and composition of domain action/config controllers. |
| Collector ops general actions | `src/components/settings/use-collector-ops-general-actions.ts` | Pending flush, failed retry, daily Markdown generation, daily Markdown copy, and related action loading flags. |
| Collector ops daemon actions | `src/components/settings/use-collector-ops-daemon-actions.ts` | Collector daemon start/stop/run-once commands and daemon command output binding. |
| Collector ops WeChat agent actions | `src/components/settings/use-collector-ops-wechat-agent-actions.ts` | WeChat agent start/stop/run/batch, health/self-heal, dedup reset, capture preview, and OCR preview commands. |
| Collector ops WeChat agent config controller | `src/components/settings/use-collector-ops-wechat-agent-config.ts` | WeChat agent hotspot/menu-offset text state, numeric config editing, config validation, and config persistence. |
| Collector ops route metrics | `src/components/settings/use-collector-ops-route-metrics.ts` | WeChat batch route/source/OCR quality counters, recovery counters, skip/failure metrics, and batch progress derivation. |
| Collector ops panel utilities | `src/components/settings/collector-ops-panel-utils.ts` | Collector operations formatting, route coverage labels/classes, short text, byte formatting, and WeChat hotspot point parsing. |
| Collector ops daemon section | `src/components/settings/collector-ops-daemon-section.tsx` | Collector daemon status presentation, daemon start/stop/run actions, source-health cards, recently collected rows, and daemon log tail rendering. |
| Collector ops general section | `src/components/settings/collector-ops-general-section.tsx` | Collector refresh, pending flush, failed retry, daily Markdown generation/copy, 24h status metrics, failed-item table, and daily Markdown textarea. |
| Collector ops WeChat agent composition | `src/components/settings/collector-ops-wechat-agent-section.tsx` | WeChat agent section ordering and composition across status, batch, logs, preview/OCR, and configuration. |
| Collector ops WeChat agent status section | `src/components/settings/collector-ops-wechat-agent-status-section.tsx` | WeChat agent run controls, health/self-heal actions, status metrics, and dedup reset summary. |
| Collector ops WeChat agent batch section | `src/components/settings/collector-ops-wechat-agent-batch-section.tsx` | Segmented batch progress, route-quality metrics, recovery counters, live checkpoint details, newly ingested item cards, and tokenized batch presentation surfaces. |
| Collector ops WeChat agent log section | `src/components/settings/collector-ops-wechat-agent-log-section.tsx` | Last-cycle error and WeChat agent log-tail rendering. |
| Collector ops WeChat agent preview section | `src/components/settings/collector-ops-wechat-agent-preview-section.tsx` | Capture preview image and OCR quality/body/keyword preview rendering. |
| Collector ops WeChat agent config section | `src/components/settings/collector-ops-wechat-agent-config-section.tsx` | WeChat agent profile, coordinates, capture-region, hotspot/menu-offset, and health-threshold configuration controls. |
| Collector ops stat card | `src/components/settings/collector-ops-stat-card.tsx` | Small reusable metric card used by collector operations presentation sections. |

Current frontend hotspots still requiring future slices:

| File | Approx. size | Risk |
| --- | ---: | --- |
| `src/components/settings/collector-ops-panel-copy.ts` | 954 lines | Large localization map is isolated from rendering and initialized as a module-level constant; future risk is translation breadth, not behavior coupling. |
| `src/components/settings/use-collector-ops-wechat-agent-actions.ts` | 251 lines | WeChat agent command controller is focused, but may split into status/config/batch/OCR action hooks if command breadth grows. |
| `src/components/knowledge/knowledge-detail-card.tsx` | 490 lines | Knowledge detail is no longer a 1,800+ line hotspot after prior section extraction, but it still combines edit form, embedded research report, commercial intelligence, review queue, and related-entry presentation; future slices should split by section before adding more behavior. |
| `src/components/session/session-summary-panel.tsx` | 1,291 lines | Session summary is now tokenized for the current theme scan, but still combines collector snapshots, digest cards, research recommendations, exports, and watchlist priority rendering; future slices should extract section components/controllers if it grows. |
| `src/components/research/use-research-topic-workspace-controller.ts` | 482 lines | Topic workspace data loading and derived compare/entity/timeline state is separated from rendering; future risk is only controller growth as more timeline actions are added. |
| `src/components/research/research-topic-workspace.tsx` | 279 lines | Topic workspace page shell is now mostly hero, latest-version summary, and section composition. |
| `src/components/research/use-research-center-controller.ts` | 282 lines | Research center controller is now a thin aggregation hook; remaining risk is cross-section prop bundle growth if new domains are added without a controller boundary. |
| `src/lib/api/type-contracts/research-report.ts` | 524 lines | Report DTOs are now separated from delivery/workspace/watchlist/evaluation/experiment/retrieval contracts; future slices can split report quality/readiness if this file grows. |
| `src/components/inbox/research-report-card.tsx` | 615 lines | Parent card now owns top-level report presentation composition and uses semantic theme tokens for its primary shell/summary surfaces; downstream report sections have moved state tones to semantic tokens, leaving presentation density as the main risk. |
| `src/components/inbox/inbox-form.tsx` | 1,638 lines | Pure research configuration and source-tier behavior is now extracted and tested; remaining risk is presentation/state breadth, so future work should split visible form/result sections rather than duplicate model logic. |
| `src/components/research/research-markdown-archive-viewer.tsx` | 1,097 lines | Markdown parsing and comparison are now extracted and tested; remaining risk is dense presentation/export orchestration, suitable for section-component extraction when the UI changes. |

## Next Slices

- Keep `research_service.py` as a compatibility facade only. All statically unreferenced private wrappers and direct owner-test calls to facade-private functions are removed; future retirement should happen only when a real external caller or compatibility alias can be deleted safely.
- Keep collector routes in owned modules only; `backend/app/api/collector.py` has been deleted.
- Keep the research DTO facade stable; future DTO work should only split the report contract further if quality/readiness or follow-up diagnostics grow again.
- Research Center section surface/text token migration is complete across sidebar controls, source settings, experiment control, low-quality review, results, watchlist, workspace, archives, and centralized tone helpers.
- Research archive/console, compare/topic-version, knowledge detail, session summary, Collector Ops, feed, inbox/research, research center, and settings now have semantic or dark-compatibility coverage; new components must prefer `af-*` tokens over legacy Tailwind light colors.
- Light/dark production screenshots now cover feed, inbox/research, research center, and settings with manifest theme assertions; add new routes only when they become release-critical surfaces.
