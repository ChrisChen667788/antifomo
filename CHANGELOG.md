# Changelog

## 0.4.2+20260424 - 2026-04-24

- Added a scenario/customer/vertical-scene review loop in the research workspace with direct refresh of market intelligence and solution delivery packs.
- Added standalone Markdown exports for the three-year market-intelligence pack and the solution-delivery/PPT-outline pack.
- Updated formal feasibility-study and project-proposal exports to rebuild scenario intelligence from the current delivery supplement instead of stale report-side packs.
- Preserved labeled metadata rows in formal documents so target customer, scenario, vertical scene, source count, and evidence notes remain readable in exports.
- Replaced the remote `next/font/google` Geist dependency with local fallback font stacks so `next build` succeeds in offline or restricted-network environments.
- Refreshed the GitHub-facing README, Chinese README, repository about copy, homepage link, topics, and launch/growth copy to better position the project for open-source discovery.

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
