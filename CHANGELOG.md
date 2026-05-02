# Changelog

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
