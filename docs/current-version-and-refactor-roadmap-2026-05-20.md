# Current Version, History, and Refactor Roadmap

Updated: 2026-06-05

This document is the working baseline for the next large change. It consolidates the current product state, historical version lines, completed development content, and the upcoming architecture refactor plus dark-mode redesign plan.

## Current State

Current release metadata:

- Previous stable released baseline: `1.0.0+20260520`.
- Current synced release line: `1.1.1+20260612`, adding measurable research workflow, cost-ledger, and 100-case evaluation contracts to the modular architecture baseline.
- Important local file to keep uncommitted: `backend/anti_fomo_demo.db.before-entity-quality-20260502-021530`.

Current completion status:

- WeChat-heavy local-first intake is connected end to end.
- Homepage triage can recover the latest WeChat Favorites import queue after reload.
- Research generation, compare, archive, delivery export, focus sessions, collector operations, and knowledge/commercial hub are usable product surfaces.
- Research Center is now split into a controller hook plus focused presentation sections; the page shell is mostly composition.
- Collector Ops now separates request/action orchestration from daemon and WeChat-agent presentation sections.
- Collector Ops WeChat agent presentation is now split by runtime status, batch route quality, logs, preview/OCR, and configuration.
- Research topic workspace now separates data-loading/derived compare state from entity workspace, version compare, and timeline UI sections.
- Research API DTO contracts are now split inside the research domain by report, delivery, workspace, watchlist, evaluation, experiment, and retrieval contracts.
- Research Center experiment, archive, workspace, and watchlist data loading/action controllers are now split out of the main controller hook.
- Research Center source settings, Daily Brief, report/action-card loading, and low-quality review actions are now split out of the main controller hook.
- Research Center filter/facet/view-derived state now lives in a dedicated view-model hook instead of the controller aggregation hook.
- Research report card quality/readiness/profile summary calculations now live in a dedicated view-model helper instead of the parent presentation component.
- Collector Ops now has separate action/config controllers for general operations, daemon commands, WeChat agent commands, WeChat config persistence, and route/OCR metrics.
- `research_service.py` now exposes `generate_research_report` as a thin setup/dependency facade; the generation workflow spine lives in `backend/app/services/research/generation_workflow.py` and consumes stage-scoped dependency ports.
- Report card, its downstream report sections, Collector Ops primary shells/daemon/batch surfaces, Research Center presentation sections, research archive/console surfaces, research compare/topic-version surfaces, knowledge detail, and session summary panels now consume semantic theme tokens instead of hard-coded day-mode white/slate/status surfaces.
- Global theme tokens are realigned with the earlier `v0.8.0+20260518` translucent day UI: light mode returns to the pale blue Apple-style glass baseline, while dark mode now mirrors the same glass language with low-saturation deep surfaces.
- The current `research_service.py` wrapper-retirement line removed zero-call legacy private helpers, moved tender-detail/source-query/source-document/section-delivery coverage to owned research submodules, and reduced the facade from 8,528 to 7,913 lines.
- Tracked miniapp config and documentation no longer publish the real WeChat Mini Program AppID; `miniapp/project.private.config.json` is ignored local-only config, and `npm run security:scan` is available as a pre-sync secret check.
- Solution delivery packs include architecture readiness, solution architect workbench output, and architecture-review artifacts.
- Release screenshots are currently aligned to `1.1.1+20260612` with `15/15` accepted screenshots; this backend-only baseline did not change visual surfaces.

Latest verified checks from the current work line:

- Backend collector/research modularization regression set passed.
- Research facade wrapper-retirement, source-document/section-delivery, and section-delivery dependency-seam regression subsets passed.
- Current-tree secret scan passed.
- Frontend lint for the current modularization line passed.
- Production build passed.
- `git diff --check` passed.

## Historical Version Lines

| Version line | Main development content | Status |
| --- | --- | --- |
| `0.3.x` | Research quality baseline: compare/export, archive snapshots, offline metrics, evidence-backed report quality gates, section evidence packs, and methodology playbooks. | Delivered |
| `0.4.x` | Retrieval substrate and delivery packs: persistent retrieval index, section routing, golden evaluation, three-year tender/product intelligence, delivery packs, and screenshots. | Delivered |
| `0.5.x` | RAG quality engineering and cleanup: CRAG-style retrieval correction, grounding review, schema-v2 chunks, source cleaning, entity cleanup, and reranker controls. | Delivered |
| `0.6.0` | CrossEncoder reranker and advisory delivery: reranker adapter, rebuild visualization, watchlist run history, failed-run retry notes, client brief, bidding memo, execution materials. | Delivered |
| `0.6.1` | Quality-triggered public-source expansion when self-evaluation remains weak. | Delivered |
| `0.6.2` - `0.6.4` | Diagnostics control plane: solution/proposal scoring, self-review/self-repair, A/B controls, follow-up delta evaluation, export trend comparison, cache/rebuild panels. | Delivered |
| `0.6.5` - `0.6.7` | Persistent experiment orchestration: frozen cohorts, locked baselines, gate history, rollout manifests, activation/revocation, active policy registry. | Delivered |
| `0.6.8` - `0.6.10` | Runtime strategy activation: runtime snapshots, effective runtime config, report-generation strategy injection, fallback visibility. | Delivered |
| `0.6.11` | Release-grade GitHub documentation and screenshot coverage across primary surfaces. | Delivered |
| `0.7.0` | Focus collection reliability and source-health operations. | Delivered |
| `0.8.0` | Solution architecture readiness: scoring, blueprint layers, non-functional requirements, risks, assumptions, stakeholder questions, validation actions. | Delivered |
| `0.8.1` | WeChat Favorites import and review queue: preview/import, dedupe, batch persistence, queue recovery, failed-item retry, homepage swipe triage. | Delivered as part of `1.0.0+20260520` |
| `0.9.0` | Solution architect workbench: customer scenarios, stakeholder maps, decision criteria, validation actions, next-meeting agendas. | Delivered as part of `1.0.0+20260520` |
| `1.0.0` | Local-first WeChat-to-solution baseline connecting intake, triage, evidence-backed research, architecture readiness, architect workbench, migrations, docs, and validation. | Delivered |
| `1.1.0` | Modular architecture and semantic theme baseline: architecture-review artifacts, research/collector workflow decomposition, feature clients/controllers, report/knowledge/session panel splits, and semantic theme-token migration. | Delivered as `1.1.0+20260602` |

## Current Module Reality

The system already has useful separation, but several areas have grown large enough to need deliberate modularization before adding more features.

Backend strengths:

- API routers are split by surface: items, collector, research, knowledge, sessions, tasks, preferences, focus, mobile, WorkBuddy.
- Persistence models are separated into entity files.
- Service files already represent domain areas: collector, item processing, research, retrieval, experiments, delivery quality, knowledge, sessions.
- Tests cover the main product seams.

Backend risks:

- Some service files have become orchestration hubs that contain parsing, domain logic, persistence coordination, and export formatting in one place.
- `research_service.py`, `research_solution_intelligence_service.py`, and collector-related services are vulnerable to continued feature accretion.
- DTO/schema growth is concentrated in a few large files.
- API routers sometimes know too much about service internals and response assembly.

Frontend strengths:

- Routes are already separated by Next.js app pages.
- Major product surfaces have component folders.
- API typing is centralized in `src/lib/api.ts`.
- Preferences and i18n have shared providers/helpers.

Frontend risks:

- `src/lib/api.ts` is becoming a broad contract file for every feature.
- Some UI components are doing data orchestration, queue state, rendering, and side effects together.
- Many visual classes use hard-coded light-mode Tailwind colors, so theme variables cannot fully control dark-mode output.
- The current glass/gradient visual language is shared across day and night, making the two modes feel like tint changes rather than distinct designs.

## Refactor Principles

The next refactor should follow the spirit of The Mythical Man-Month and software industry practice:

- Preserve conceptual integrity: one architecture vocabulary, one dependency direction, one design-system contract.
- Prefer clear module boundaries over broad rewrites.
- Avoid the second-system effect: do not rebuild everything because the current code is imperfect.
- Keep orchestration thin and move domain decisions into cohesive modules.
- Make interfaces explicit: DTOs, service contracts, repository boundaries, and UI feature boundaries should be stable enough to test.
- Optimize for change isolation: a collector change should not require touching research delivery UI; a theme change should not require editing every business component.
- Use incremental migration with compatibility adapters and regression tests.

## Target Architecture Direction

Backend target layers:

- `api`: FastAPI routers, validation entrypoints, HTTP-only concerns.
- `application`: use cases and orchestration, one file/module per workflow.
- `domain`: business rules, scoring, parsing decisions, delivery-pack generation, quality policies.
- `persistence`: repositories and query helpers around SQLAlchemy models.
- `infrastructure`: browser extraction, WeChat automation, LLM calls, file storage, external adapters.
- `schemas`: API DTOs, split by feature and version where needed.
- `shared`: language normalization, text utilities, source normalization, test factories.

Backend candidate module boundaries:

- `collector`: URL/text/file/WeChat Favorites/source-daemon intake, import batches, source health.
- `items`: item lifecycle, processing runtime, feedback, recommendation, interpretation.
- `research`: research generation, retrieval, topic workspace, archives, compare snapshots.
- `delivery`: market intelligence, solution delivery packs, architecture readiness, architect workbench, exports.
- `experiments`: evaluation cohorts, gates, runtime strategy activation.
- `knowledge`: saved knowledge, intelligence, merge, commercial hub.
- `execution`: focus sessions, session summaries, tasks, briefs, watchlist automation.

Frontend target layers:

- `app`: route shells only.
- `features/<feature>`: feature-specific components, hooks, API adapters, local state.
- `components/ui`: reusable primitives with semantic tokens only.
- `components/layout`: shell, navigation, page scaffolding.
- `lib/api/<feature>`: typed API clients split by domain, re-exported through a compatibility facade during migration.
- `lib/theme`: semantic tokens, theme utilities, visual-mode helpers.
- `lib/testing` or `test-utils`: fixtures for product surfaces.

## Refactor Work Plan

### Phase 1: Architectural Inventory and Fitness Tests

Goal: map current dependencies and create guardrails before moving files.

Work:

- Produce a dependency map for backend services, API routers, frontend components, and API clients.
- Identify files that exceed acceptable responsibility size or coupling.
- Add smoke-level contract tests around collector import, item list/reprocess, solution delivery generation, research report card rendering, and theme switching.
- Define allowed dependency direction in docs and lint/test checks where practical.

Acceptance:

- A documented module map exists.
- Top refactor targets are ranked by risk and payoff.
- Existing user workflows are covered by tests before structural movement starts.

### Phase 2: Backend Modularization

Goal: split large service hubs without changing behavior.

Work:

- Move WeChat Favorites parsing/import batch logic into a collector import submodule.
- Move solution delivery architecture workbench logic into a delivery/architecture package.
- Introduce repository/query helpers for import batches, items, feedback, and research delivery artifacts.
- Keep API response shape stable.
- Maintain compatibility imports until callers are migrated.

Acceptance:

- Collector, delivery, research, and item workflows have clear application-service entrypoints.
- Existing targeted and backend full tests pass.
- No public API route shape changes unless explicitly versioned.

### Phase 3: Frontend Feature Modularization

Goal: make product surfaces composable and themeable.

Work:

- Split `src/lib/api.ts` into feature clients while keeping a compatibility export.
- Extract feed import queue logic into a feature hook.
- Extract research report delivery panels into focused subcomponents.
- Introduce shared UI primitives for panels, metric cards, status badges, segmented controls, list rows, and action bars.

Acceptance:

- Route pages remain thin.
- Feed, inbox/research, collector, settings, and knowledge surfaces can evolve independently.
- TypeScript build and lint pass after each migration slice.

### Phase 4: Theme System and Dark-Mode Redesign

Goal: make day mode and night mode intentionally different design systems, not a light palette with darker variables.

Current theme problems:

- `html[data-af-theme="dark"]` defines variables, but many components still use hard-coded `bg-white`, `text-slate-*`, `border-slate-*`, `bg-cyan-*`, `bg-emerald-*`, and similar light-mode classes.
- Glass surfaces and background effects are reused across modes, so night mode lacks a distinct information hierarchy.
- Some dark-mode text/background combinations depend on Tailwind defaults rather than semantic contrast tokens.
- Navigation, cards, panels, forms, badges, and callouts do not have consistent dark-mode elevation rules.

Dark-mode design direction:

- Day mode: clear, airy, operational, high readability, restrained highlights.
- Night mode: deep neutral base, lower glare, high-contrast text, fewer decorative effects, stronger panel depth, purposeful accent colors.
- Replace visual decoration with semantic surfaces: page, shell, surface, elevated, inset, selected, hover, muted, critical, warning, success, info.
- Avoid relying on glass and gradients as the main visual identity.
- Use dark-mode screenshots as a release gate, not a preference afterthought.

Implementation plan:

- Add semantic CSS tokens for `surface`, `surface-elevated`, `surface-muted`, `surface-selected`, `text-primary`, `text-secondary`, `text-tertiary`, `border-subtle`, `border-strong`, `accent`, `accent-soft`, `danger`, `warning`, `success`, and `info`.
- Replace hard-coded light Tailwind colors in shared components first.
- Build UI primitives that consume tokens through class names or CSS variables.
- Migrate major screens one by one: layout/nav, feed, inbox/research card, collector, settings, knowledge.
- Add screenshot capture for dark mode and compare day/night primary surfaces.
- Verify contrast, text fitting, selected states, hover states, disabled states, and focus rings.

Acceptance:

- Night mode has a visibly distinct visual system.
- No major surface depends on hard-coded light backgrounds for primary panels.
- Core pages render readable screenshots in both modes.
- `npm run lint`, `npm run build`, targeted UI checks, and screenshot checks pass.

## Near-Term Version Plan

### `1.1.x`: Modular Architecture Hardening

- Continue shrinking remaining orchestration shells only where there is clear ownership or testability gain.
- Keep architecture fitness checks and the module ownership map current as new feature seams are added.
- Preserve public behavior and API compatibility unless a route or DTO is explicitly versioned.

### `1.2.0`: Day/Night Design System Refresh

- Introduce semantic theme tokens.
- Rebuild dark mode as a distinct product surface.
- Migrate primary pages and refresh screenshot gates.

### Later

- Add richer architecture-export formats: ADR table export, dependency workshop checklist, stakeholder brief, and customer technical workshop agenda.
- Add plugin/extensibility boundaries after core modules are stable.
- Add CI-level architecture checks for forbidden imports and cross-module coupling.

## Refactor Execution Log

### 2026-05-20: Collector Import Slice 1

Scope:

- Extracted WeChat Favorites parsing and import-batch assembly into `backend/app/services/collector_imports/wechat_favorites.py`.
- Kept `collector_multiformat_service.py` as a compatibility facade for the import workflow while it still owns the shared Item persistence helper.
- Pointed the collector preview API at the new pure parsing module.
- Preserved existing API request/response shapes and existing test entrypoints.

Module boundary decision:

- `collector_imports.wechat_favorites` owns WeChat export decoding, URL normalization, text-block candidate extraction, candidate DTOs, import result accounting, and `CollectorImportBatch` creation.
- `collector_multiformat_service` owns shared collector persistence helpers, RSS/newsletter/document/Youtube ingestion, and temporary compatibility wrappers.
- `api.collector` should call pure parsing modules directly for preview-style endpoints, and call application-level wrappers when database persistence is involved.

Verified:

- `python3 -m py_compile backend/app/services/collector_multiformat_service.py backend/app/services/collector_imports/wechat_favorites.py backend/app/api/collector.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_multiformat_collector_service.py backend/tests/test_item_schema.py backend/tests/test_sqlite_compat.py`

### 2026-05-20: Delivery Architecture Slice 2

Scope:

- Extracted solution architecture readiness, solution architect workbench, capability-to-architecture matrix, ADR records, and integration dependency diagnostics into `backend/app/services/delivery/solution_architecture.py`.
- Reduced `research_solution_intelligence_service.py` back toward orchestration: market intelligence, delivery-pack assembly, quality review, markdown export, and compatibility exports.
- Preserved existing `build_solution_architecture_readiness` and `build_solution_architect_workbench` import compatibility through the research solution intelligence service.
- Preserved existing solution delivery pack API and markdown output shape.

Module boundary decision:

- `delivery.solution_architecture` owns architecture scoring, architecture blueprint construction, stakeholder/problem-map generation, decision criteria, capability mapping, ADRs, and integration dependency diagnostics.
- `research_solution_intelligence_service` owns research-derived market intelligence and delivery-pack orchestration, then delegates architecture enrichment to the delivery module.
- Markdown serialization can remain with the delivery pack exporter until a later export-format split, because it serializes the full assembled pack rather than owning architecture decisions.

Verified:

- `python3 -m py_compile backend/app/services/research_solution_intelligence_service.py backend/app/services/delivery/solution_architecture.py backend/app/services/work_task_service.py backend/app/api/research.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py`

### 2026-05-20: Delivery Market Intelligence Slice 3

Scope:

- Extracted market intelligence, three-year tender extraction, buyer/vendor/agency/project-code parsing, product catalog extraction, technical-parameter catalog extraction, retrieval correction, and market intelligence markdown serialization into `backend/app/services/delivery/market_intelligence.py`.
- Reduced `research_solution_intelligence_service.py` further into a solution delivery orchestration layer: advisory artifacts, delivery pack assembly, architecture enrichment delegation, and full delivery markdown export.
- Pointed pure market-intelligence callers in `api.research`, `work_task_service`, and targeted tests directly at `delivery.market_intelligence`.
- Preserved existing compatibility imports from `research_solution_intelligence_service` for `build_market_intelligence_pack` and `build_market_intelligence_markdown`.

Module boundary decision:

- `delivery.market_intelligence` owns public-source qualification, three-year tender/project extraction, product and technical-parameter catalogs, external search-query recommendations, and standalone market intelligence markdown.
- `research_solution_intelligence_service` owns solution-delivery composition after market intelligence is already built.
- `work_task_service` and `api.research` should use the market module directly when they only need market intelligence, and use the solution intelligence service when they need the complete delivery pack.

Verified:

- `python3 -m py_compile backend/app/services/research_solution_intelligence_service.py backend/app/services/delivery/market_intelligence.py backend/app/services/delivery/solution_architecture.py backend/app/services/work_task_service.py backend/app/api/research.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py`

### 2026-05-21: Delivery Materials Slice 4

Scope:

- Extracted delivery outlines, advisory-grade artifacts, and full solution delivery markdown serialization into `backend/app/services/delivery/solution_materials.py`.
- Reduced `research_solution_intelligence_service.py` into a thinner orchestration layer: scenario/customer resolution, market intelligence delegation, intelligence summary and clarification assembly, evidence policy, delivery pack assembly, quality review, architecture enrichment, and final export assignment.
- Preserved existing compatibility imports from `research_solution_intelligence_service` for `build_solution_delivery_markdown`, `build_market_intelligence_pack`, and `build_market_intelligence_markdown`.
- Preserved existing solution delivery pack schemas and export markdown shape.

Module boundary decision:

- `delivery.solution_materials` owns human-facing delivery material generation: feasibility-study outline, project-proposal outline, client PPT outline, advisory artifact markdown, and complete delivery markdown serialization.
- `research_solution_intelligence_service` owns the use-case orchestration only and should not contain material templates or markdown formatting rules.
- Future delivery formats should extend `delivery.solution_materials` or a narrower exporter module instead of adding serializers back into the orchestration service.

Verified:

- `python3 -m py_compile backend/app/services/research_solution_intelligence_service.py backend/app/services/delivery/solution_materials.py backend/app/services/delivery/market_intelligence.py backend/app/services/delivery/solution_architecture.py backend/app/services/work_task_service.py backend/app/api/research.py backend/app/services/research_service.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py`

### 2026-05-21: Architecture Fitness and Theme Foundation Slice 5

Scope:

- Added `docs/module-ownership-map-2026-05-21.md` to document backend/frontend ownership, dependency direction, current hotspots, and next slices.
- Added backend architecture fitness tests in `backend/tests/test_architecture_boundaries.py` so delivery modules cannot import the solution orchestration service or API layer, and `research_solution_intelligence_service.py` stays a thin orchestrator.
- Added pure delivery-material tests in `backend/tests/test_delivery_solution_materials.py` for delivery outlines, advisory artifacts, and delivery markdown serialization.
- Extracted the frontend API transport layer into `src/lib/api/client.ts`, keeping `src/lib/api.ts` as a compatibility facade for existing callers.
- Reworked the shared theme foundation in `src/app/globals.css` around semantic surface/text/border/accent tokens, with a distinct deep-neutral dark mode and less glass/gradient dependency.
- Migrated layout navigation, page headings, and common settings controls to semantic theme primitives.

Module boundary decision:

- Architecture rules should be executable tests, not only documentation.
- Frontend feature-client migration should start at the transport layer and keep the existing `src/lib/api.ts` exports stable until feature clients are split.
- Dark-mode redesign starts with shared tokens and layout primitives before migrating large product panels.

Verified:

- `python3 -m py_compile backend/tests/test_architecture_boundaries.py backend/tests/test_delivery_solution_materials.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_architecture_boundaries.py backend/tests/test_delivery_solution_materials.py backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py`

### 2026-05-21: Research Markdown and Items Client Slice 6

Scope:

- Extracted full research-report markdown serialization from `backend/app/services/research_service.py` into `backend/app/services/research/report_markdown.py`.
- Preserved compatibility for existing callers that import `build_research_report_markdown` from `research_service.py`.
- Extracted the first frontend feature API client into `src/lib/api/items.ts`, covering item list/detail/create, preferences, diagnostics, feedback, reprocess, interpretation, and add-to-knowledge calls.
- Kept `src/lib/api.ts` as a compatibility facade by re-exporting the extracted item client functions.
- Migrated Feed status and Feed deck business panels from hard-coded light Tailwind panel classes to semantic theme primitives and shared chip/panel/progress classes.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new research markdown and items API ownership.

Module boundary decision:

- Research markdown export is presentation/serialization logic and should not live inside the primary research generation service.
- Feature API clients should migrate one domain at a time behind the existing facade to avoid broad component churn.
- Theme migration should start with high-frequency business panels and shared primitives before attempting the largest research/inbox surfaces.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/report_markdown.py backend/app/services/research_solution_intelligence_service.py backend/tests/test_architecture_boundaries.py backend/tests/test_delivery_solution_materials.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_architecture_boundaries.py backend/tests/test_delivery_solution_materials.py backend/tests/test_research_solution_intelligence_service.py backend/tests/test_research_solution_delivery_exports.py backend/tests/test_research_section_evidence.py backend/tests/test_research_report_storage_rewrite.py`
- `npm run lint`
- `npm run build`

### 2026-05-21: Research, Knowledge, Collector Clients and Inbox Theme Slice 7

Scope:

- Extracted `src/lib/api/research.ts` from the API facade, covering research report/job/conversation, daily brief, workspace, source settings, quality review queue, evaluation, experiments, retrieval, solution delivery, compare snapshots, markdown archives, watchlists, entities, tracking topics, save, and action-plan calls.
- Extracted `src/lib/api/knowledge.ts` from the API facade, covering knowledge entries, dashboard, account intelligence, opportunities, markdown, related entries, review queue resolution, merge, merge preview, and rules.
- Extracted `src/lib/api/collector.ts` from the API facade, covering collector status/daemon, WeChat agent operations, failed queues, source and feed management, newsletter/file/YouTube ingest, and WeChat Favorites import batches.
- Kept `src/lib/api.ts` as the compatibility facade with existing type exports and re-exports from the new feature clients, reducing the facade from 4,411 to 3,129 lines.
- Migrated the main inbox intake panel, keyword research panel, research report card, and research action cards panel away from hard-coded slate/white surfaces toward semantic theme tokens and shared button/input/surface primitives.
- Updated `docs/module-ownership-map-2026-05-21.md` with ownership rows and hotspot sizes for the newly extracted frontend clients.

Module boundary decision:

- Frontend feature clients own endpoint construction and request payload shaping for their domain, while `src/lib/api.ts` remains the stable public facade until component imports are ready to move.
- API types remain in the facade for now to avoid a high-risk type-file churn; a later slice can move contracts into `src/lib/api/types.ts` once the remaining feature clients are extracted.
- Inbox and research-report surfaces should consume semantic surface/text/border tokens first; detailed status tones can be normalized in later component-splitting slices.

Verified:

- `npm run lint`
- `npm run build`

### 2026-05-22: Report Card Remaining Sections and API Contract Domains Slice 10

Scope:

- Moved report-card readiness/playbook rendering into `src/components/inbox/research-report-readiness-section.tsx`.
- Moved strategic outlook, competition analysis, ranked entity panels, peer movement panels, and highlight panels into `src/components/inbox/research-report-strategic-section.tsx`.
- Moved the final report source list into `src/components/inbox/research-report-source-list-section.tsx`.
- Reduced `src/components/inbox/research-report-card.tsx` from 1,341 to 909 lines and kept it focused on top-level derived state, summary panels, and section orchestration.
- Split `src/lib/api/types.ts` into feature-domain contracts under `src/lib/api/type-contracts/` for items, research, knowledge, collector, sessions, tasks, and system settings.
- Kept `src/lib/api/types.ts` as the stable seven-line type re-export entry so existing feature clients and UI callers do not churn.
- Updated report shared styles to `styled-jsx global` so split report section components still receive the shared report surface classes.

Module boundary decision:

- Report-card section components now own cohesive presentation blocks; the parent should only retain shared calculations until those can move into presenter helpers.
- API DTO ownership now follows the same feature-domain boundary as API clients, while `@/lib/api/types` remains the stable public import path.
- The research DTO file remains the largest contract because it spans reports, retrieval, experiments, delivery, tracking topics, watchlists, archives, and evaluation; future splits should happen inside that domain, not by reopening the top-level facade.

Verified:

- `npm run lint`
- `npm run build`

### 2026-05-21: Sessions, Tasks, System Clients and Report Card Components Slice 8

Scope:

- Extracted `src/lib/api/sessions.ts` from the API facade, covering focus sessions, session artifacts, todo calendar preview/import, and focus-assistant plan/action calls.
- Extracted `src/lib/api/tasks.ts` from the API facade, covering WorkBuddy health/webhook and async task create/detail calls.
- Extracted `src/lib/api/system.ts` from the API facade, covering API health, LLM config, and LLM dry-run calls.
- Kept `src/lib/api.ts` as the compatibility facade with type exports and feature-client re-exports, reducing it from 3,129 to 2,969 lines.
- Started decomposing `src/components/inbox/research-report-card.tsx` by extracting same-file subcomponents for solution delivery material rendering and source/diagnostics rendering.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new feature clients and the updated report-card boundary status.

Module boundary decision:

- Session/focus-assistant calls belong together because they operate on the active focus workflow and session artifacts.
- WorkBuddy webhooks and async task calls share an execution/export responsibility and now live in the task client.
- System health and LLM settings/dry-run calls are operational settings concerns and should not remain mixed into product feature clients.
- Report-card component extraction should stabilize props inside the existing file before moving subcomponents into separate files, because delivery and diagnostics still share report DTOs and display policy helpers.

Verified:

- `npm run lint`
- `npm run build`

### 2026-05-21: API Types and Report Card Boundaries Slice 9

Scope:

- Moved shared frontend API DTO contracts from `src/lib/api.ts` into `src/lib/api/types.ts`.
- Updated extracted feature clients to import DTOs from `@/lib/api/types`, leaving `src/lib/api.ts` as a 179-line compatibility facade with feature-client re-exports and `toFeedCardLabel`.
- Moved the previously same-file report-card delivery section into `src/components/inbox/research-report-delivery-section.tsx`.
- Moved the report-card source/diagnostics section into `src/components/inbox/research-report-sources-diagnostics-section.tsx` with shared report-section types in `src/components/inbox/research-report-section-types.ts`.
- Split the report-card insights, review queue, and technical appendix areas into `research-report-insights-section.tsx`, `research-report-review-queue-section.tsx`, and `research-report-appendix-section.tsx`.
- Reduced `src/components/inbox/research-report-card.tsx` from 2,475 to 1,341 lines while keeping it as the parent orchestration component.

Module boundary decision:

- API request functions and API DTO contracts are now separate frontend ownership areas: feature clients own endpoint behavior, while `api/types.ts` owns shared wire contracts.
- Report-card subcomponents own cohesive rendering sections; the parent card keeps shared derived state and helper functions until the remaining strategic/readiness/source-list areas are split.
- A later type split should divide `api/types.ts` by feature domain instead of re-expanding the compatibility facade.

Verified:

- `npm run lint`
- `npm run build`

### 2026-05-22: Research Service, Research Center, and Collector Ops Slice 11

Scope:

- Extracted public web search concerns from `backend/app/services/research_service.py` into `backend/app/services/research/web_search.py`, including the `SearchHit` model, DuckDuckGo/Bing result parsers, SSL fallback URL opening, and result deduplication.
- Kept `research_service.py` compatibility for callers and tests that patch `SearchHit` or `_search_public_web`, while reducing the service from 15,671 to 15,435 lines.
- Extracted the Research Center Markdown archive presentation into `src/components/research/research-center-markdown-archives-section.tsx`, reducing `research-center.tsx` from 4,980 to 4,801 lines.
- Extracted collector daemon and WeChat agent ops response mapping into `backend/app/api/collector_ops_serializers.py`, reducing `backend/app/api/collector.py` from 2,552 to 2,256 lines.
- Extracted collector ops panel formatting, coverage labels, byte formatting, text truncation, and WeChat point parsing into `src/components/settings/collector-ops-panel-utils.ts`.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new backend/frontend ownership rows and current hotspot sizes.

Module boundary decision:

- Research public web search is an adapter concern and should not live inside the primary report generation service.
- Research Center archive card rendering is a cohesive presentation block; the parent should own state and data derivation, not card markup.
- Collector ops response mapping belongs to an API presenter module so the router can focus on dependency checks, service invocation, and HTTP errors.
- Collector ops panel utility functions are deterministic formatting/parsing helpers and should not remain inside the stateful panel component.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ops_serializers.py backend/app/services/research_service.py backend/app/services/research/web_search.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_route_quality.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_multiformat_collector_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_browser_content_extractor_chain.py`
- `npm run lint`
- `npm run build`

### 2026-05-22: Collector Source and Feed Route Slice 12

Scope:

- Extracted collector source CRUD/import endpoints and RSS feed management endpoints from `backend/app/api/collector.py` into `backend/app/api/collector_sources.py`.
- Added `backend/app/api/collector_url_utils.py` for shared collector API URL validation, source URL normalization, and text cleanup so ingest routes and source routes do not duplicate URL policy.
- Registered the new source/feed router in `backend/app/main.py` under the existing `/api/collector` prefix, preserving public endpoint paths.
- Reduced `backend/app/api/collector.py` from 2,256 to 1,890 lines; source/feed routes now own their own serializers, lookup helpers, and locked-SQLite flush retry.
- Updated `docs/module-ownership-map-2026-05-21.md` with source/feed API ownership, URL utility ownership, and current hotspot sizes.

Module boundary decision:

- Source/feed management is a separate collector API subdomain from content ingest/OCR and daemon operations.
- URL normalization is shared API policy and should be imported by route modules instead of reimplemented in each route file.
- `collector.py` remains the compatibility home for ingest/OCR/status routes and the existing tests that monkeypatch `_mark_source_collected`.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_sources.py backend/app/api/collector_url_utils.py backend/app/main.py`
- `.venv311/bin/python` route registry check for `/api/collector/sources`, `/api/collector/feeds`, `/api/collector/rss/sources`, and `/api/collector/rss/pull`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_route_quality.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_multiformat_collector_service.py`
- `npm run lint`

### 2026-05-24: Research Storage and Collector Ingest/OCR Slice 13

Scope:

- Extracted research source-document DTO/conversion logic from `backend/app/services/research_service.py` into `backend/app/services/research/source_documents.py`.
- Extracted stored research report section aliases, persisted-source reconstruction, and stored-report-to-result mapping into `backend/app/services/research/report_storage.py`.
- Kept `research_service.py` compatibility wrappers for existing tests and callers while reducing it from 15,435 to 15,333 lines.
- Extracted newsletter, uploaded document, and YouTube transcript ingest endpoints from `backend/app/api/collector.py` into `backend/app/api/collector_external_ingest.py`.
- Extracted OCR preview quality gates, crop retry profiles, and OCR retry orchestration into `backend/app/api/collector_ocr.py`, leaving compatibility wrappers in `collector.py` for current tests and route handlers.
- Registered the new external ingest router in `backend/app/main.py`, preserving public endpoint paths.
- Reduced `backend/app/api/collector.py` from 1,890 to 1,599 lines after source/feed, ops serialization, external ingest, and OCR helper extraction.
- Updated `docs/module-ownership-map-2026-05-21.md` with research storage/source-document, collector external ingest, collector OCR helper ownership, and current hotspot sizes.

Module boundary decision:

- Persisted report reconstruction and source-document conversion are storage/materialization concerns; research generation should call them through a narrow adapter instead of owning the mapping rules.
- External collector ingest endpoints are a separate API subdomain from browser/plugin/URL ingest, OCR HTTP entrypoints, and daemon operations.
- OCR quality and retry heuristics are deterministic helper policy and should be testable outside the main collector router; the router keeps thin wrappers only to preserve monkeypatch-compatible behavior while the split proceeds.
- `collector.py` remains the compatibility home for browser/plugin/URL ingest, OCR route entrypoints, retry/status flows, and WeChat agent operations until those domains are split in later slices.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ocr.py backend/app/api/collector_external_ingest.py backend/app/api/collector_sources.py backend/app/main.py backend/app/services/research_service.py backend/app/services/research/report_storage.py backend/app/services/research/source_documents.py`
- `.venv311/bin/python` route registry check for `/api/collector/sources`, `/api/collector/feeds`, `/api/collector/newsletter/ingest`, `/api/collector/files/upload`, and `/api/collector/youtube/ingest`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_route_quality.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_multiformat_collector_service.py`
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-25: Research Service Thin-Orchestrator Slice 24

Scope:

- Extracted section confidence/scoring helpers from `backend/app/services/research_service.py` into `backend/app/services/research/section_quality.py`, covering section evidence links, evidence quotas, confidence tone, insufficiency profile, and next verification steps.
- Extracted research commercial summary, technical appendix, scenario comparison, and review queue construction into `backend/app/services/research/delivery_materials.py`.
- Extracted follow-up diagnostics helpers into `backend/app/services/research/followup_diagnostics.py`, covering follow-up context shaping, scope-hint rebuild, query decomposition, impacted-section scoring, and prompt-context rendering.
- Extracted stored-report entity canonicalization into `backend/app/services/research/stored_entity_canonicalization.py`, covering canonical entity names, ranked-entity deduplication, stored result/report canonicalization, and candidate-profile company-name cleanup.
- Kept compatibility wrappers in `research_service.py` for existing tests, call sites, and monkeypatch seams while reducing it from 10,047 to 8,961 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new research module ownership rows and current hotspot size.

Module boundary decision:

- Section confidence and evidence quota rules now belong to the section-quality domain instead of the orchestration service.
- Research delivery materials are separate from delivery enrichment: enrichment decides when to refresh report delivery fields, while `delivery_materials.py` owns how those fields are generated.
- Follow-up diagnostics own second-pass scope reconstruction and impacted-section scoring; generation execution only consumes rendered prompt context through wrappers.
- Stored-report entity canonicalization owns persisted entity cleanup and ranked-entity dedupe, while `research_service.py` keeps existing compatibility wrappers for older callers.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/*.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_research_low_quality_audit.py backend/tests/test_architecture_boundaries.py`
- `git diff --check`

### 2026-05-25: Research Center Derived Data Slice 25

Scope:

- Extracted research-center derived data and formatting helpers from `src/components/research/research-center.tsx` into `src/components/research/research-center-utils.ts`.
- Moved entry normalization, preview extraction, report metadata/readiness/source diagnostic parsing, ranked preview fallback, quality/status tone helpers, watchlist schedule/time formatting, action phase parsing, and topic/archive route builders into the new utility module.
- Kept `research-center.tsx` focused on request state, user actions, and rendering while reducing it from 4,801 to 4,199 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new research center utility owner and current hotspot size.

Module boundary decision:

- Pure derived data and presentation labels should live outside the dashboard component so future UI section extraction does not duplicate metadata parsing or status-tone rules.
- `research-center.tsx` still owns state and rendering for now; the next slices should extract request state/hooks and larger UI sections.

Verified:

- `npm run lint`
- `git diff --check`

### 2026-05-25: Research Center Controller Slice 26

Scope:

- Extracted Research Center request/state orchestration from `src/components/research/research-center.tsx` into `src/components/research/use-research-center-controller.ts`.
- Moved initial data loading, research-card refresh, low-quality queue refresh, offline evaluation refresh, retrieval-index refresh/rebuild, experiment control-plane actions, daily brief refresh, saved view/topic/archive operations, watchlist operations, and source toggles into the controller hook.
- Kept the page component focused on rendering while preserving existing compare, archive, experiment, watchlist, and card-list behavior.
- Reduced `research-center.tsx` from 4,199 to 3,079 lines and updated the module ownership map with the new controller boundary.

Module boundary decision:

- Network request state, retry/refresh handlers, and workflow mutations now belong to the controller hook.
- `research-center.tsx` should no longer grow new API orchestration; subsequent slices should split the remaining large UI sections into presentation components.

Verified:

- `npm run lint`
- `npm run build`

### 2026-05-25: Research Center UI Sections Slice 27

Scope:

- Extracted the large Research Center UI sections from `src/components/research/research-center.tsx` into focused presentation modules:
  - `src/components/research/research-center-experiment-control-section.tsx`
  - `src/components/research/research-center-watchlist-section.tsx`
  - `src/components/research/research-center-low-quality-review-section.tsx`
  - `src/components/research/research-center-results-section.tsx`
- Moved experiment/control-plane rendering, retrieval-index controls, delivery export diagnostics, watchlist ops, low-quality review queue, and report/action-card result rendering out of the page shell.
- Reduced `research-center.tsx` from 3,079 to 1,010 lines after this UI-section split.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new Research Center section ownership rows.

Module boundary decision:

- `research-center.tsx` now owns page composition, source settings, filters, saved views, tracking topics, and sidebar layout.
- Section components own their own rendering details and call controller-provided handlers through explicit props.
- The next Research Center slice should split source settings, saved/compare/tracking workspace cards, and daily brief/filter sidebar before changing behavior.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-25: Research Center Sidebar and Workspace Sections Slice 28

Scope:

- Extracted the remaining Research Center source-settings panel into `src/components/research/research-center-source-settings-section.tsx`.
- Extracted Daily Brief and filter/sidebar controls into `src/components/research/research-center-sidebar-controls.tsx`.
- Extracted saved compare snapshots, saved views, and tracking topics into `src/components/research/research-center-workspace-sections.tsx`.
- Kept source toggles, refresh/apply/delete/save operations, filter changes, compare links, and tracking-topic actions wired through explicit controller props.
- Reduced `research-center.tsx` from 1,010 to 377 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new Research Center section ownership rows and hotspot size.

Module boundary decision:

- `research-center.tsx` now owns page shell composition only: hero/navigation, stats, controller wiring, and section ordering.
- Sidebar controls own view-selection presentation but still consume controller state; future work should reduce prop fan-out with narrower section controllers if the behavior grows.
- Workspace cards own saved-view/topic/snapshot rendering and action buttons; they do not own data loading or mutation state.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/research/research-center-source-settings-section.tsx`
- `git diff --no-index --check /dev/null src/components/research/research-center-sidebar-controls.tsx`
- `git diff --no-index --check /dev/null src/components/research/research-center-workspace-sections.tsx`

### 2026-05-25: Research Center Props, Collector Ops Controller, and Topic Workspace Utils Slice 29

Scope:

- Reworked `src/components/research/use-research-center-controller.ts` to return section-scoped prop bundles for the Research Center hero, console, source settings, experiment controls, sidebar, archives, workspace, low-quality review, watchlist, and results sections.
- Reduced `src/components/research/research-center.tsx` from 377 to 89 lines; it now mostly owns route-level composition and hero copy.
- Extracted collector operations request/action orchestration from `src/components/settings/collector-ops-panel.tsx` into `src/components/settings/use-collector-ops-panel-controller.ts`.
- Reduced `collector-ops-panel.tsx` from 2,572 to 2,076 lines; daemon and WeChat agent rendering remain in the panel for later UI-section extraction.
- Extracted topic workspace diff/ranking/source-contribution helpers from `src/components/research/research-topic-workspace.tsx` into `src/components/research/research-topic-workspace-utils.ts`.
- Reduced `research-topic-workspace.tsx` from 2,032 to 1,574 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with new controller/helper ownership rows and refreshed hotspot sizes.

Module boundary decision:

- Research Center sections should receive coherent prop bundles instead of page-level field fan-out.
- Collector ops request state, polling, retries, daemon commands, WeChat agent commands, config persistence, and route metrics belong to the controller hook; the panel should focus on presentation.
- Topic workspace helper rules are now reusable pure utilities, so future controller or UI-section extraction can consume one shared diff/ranking/evidence policy.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-panel-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/research-topic-workspace-utils.ts`

### 2026-05-25: Collector Ops UI and Topic Workspace Controller/Sections Slice 30

Scope:

- Extracted collector daemon presentation from `src/components/settings/collector-ops-panel.tsx` into `src/components/settings/collector-ops-daemon-section.tsx`.
- Extracted WeChat agent operations presentation from `collector-ops-panel.tsx` into `src/components/settings/collector-ops-wechat-agent-section.tsx`.
- Extracted the shared collector metric card into `src/components/settings/collector-ops-stat-card.tsx`.
- Reduced `collector-ops-panel.tsx` from 2,076 to 1,106 lines; it now keeps the broader page composition plus source/import/OCR/general operations presentation.
- Extracted topic workspace data loading, version selection state, entity selection state, derived comparison panels, timeline stats, action regeneration, recap exports, and archive persistence into `src/components/research/use-research-topic-workspace-controller.ts`.
- Extracted topic normalized-entity workspace UI into `src/components/research/research-topic-entity-workspace-section.tsx`.
- Extracted side-by-side version comparison, follow-up impact, field diff, score, and source contribution UI into `src/components/research/research-topic-version-compare-section.tsx`.
- Extracted topic version/snapshot/archive timeline UI into `src/components/research/research-topic-timeline-section.tsx`.
- Reduced `research-topic-workspace.tsx` from 1,574 to 302 lines; it now mostly owns the route-level shell, latest-version summary, and section composition.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new collector and research-topic ownership rows plus refreshed hotspot sizes.

Module boundary decision:

- Collector Ops request state and mutations stay in the controller; daemon and WeChat-agent panels are presentation modules consuming that controller.
- The topic workspace hook owns data loading, mutation handlers, and derived comparison/entity/timeline state, while the page shell and sections focus on rendering.
- Entity workspace, version comparison, and timeline are separate UI domains because they evolve independently and have different action surfaces.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-daemon-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-stat-card.tsx`
- `git diff --no-index --check /dev/null src/components/research/use-research-topic-workspace-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/research-topic-entity-workspace-section.tsx`
- `git diff --no-index --check /dev/null src/components/research/research-topic-version-compare-section.tsx`
- `git diff --no-index --check /dev/null src/components/research/research-topic-timeline-section.tsx`

### 2026-05-31: Collector Ops Presentation Section Split Slice 31

Scope:

- Extracted the remaining general collector operations presentation from `src/components/settings/collector-ops-panel.tsx` into `src/components/settings/collector-ops-general-section.tsx`.
- Reduced `collector-ops-panel.tsx` from 1,106 to 982 lines; it now mostly owns localization copy, controller initialization, and section composition.
- Reworked `src/components/settings/collector-ops-wechat-agent-section.tsx` from a 792-line rendering module into a 33-line composition module.
- Extracted WeChat agent runtime controls, health display, status metrics, and dedup reset UI into `src/components/settings/collector-ops-wechat-agent-status-section.tsx`.
- Extracted segmented batch progress, route-quality metrics, recovery counters, live checkpoints, and new-item cards into `src/components/settings/collector-ops-wechat-agent-batch-section.tsx`.
- Extracted last-cycle error/log-tail rendering into `src/components/settings/collector-ops-wechat-agent-log-section.tsx`.
- Extracted capture preview and OCR quality/body/keyword preview rendering into `src/components/settings/collector-ops-wechat-agent-preview-section.tsx`.
- Extracted profile, coordinate, capture-region, hotspot/menu-offset, interval, and health-threshold controls into `src/components/settings/collector-ops-wechat-agent-config-section.tsx`.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new collector ops section owners and refreshed hotspot sizes.

Module boundary decision:

- `collector-ops-panel.tsx` should remain the route-level settings surface and not own operational markup.
- WeChat agent UI is now split by operational domain: status/health, batch route quality, logs, preview/OCR diagnostics, and configuration.
- The controller remains the single state/mutation owner, so the new presentation modules do not start their own data loading or background polling.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-general-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-status-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-batch-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-log-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-preview-section.tsx`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-wechat-agent-config-section.tsx`

### 2026-05-31: Research DTO Domain Contract Split Slice 32

Scope:

- Replaced the 1,632-line `src/lib/api/type-contracts/research.ts` monolith with a 7-line compatibility facade that re-exports domain-specific research contracts.
- Added `src/lib/api/type-contracts/research-report.ts` for report, source diagnostics, entity evidence, readiness, quality profile, follow-up diagnostics, jobs, conversations, daily brief, source settings, action cards, and save responses.
- Added `src/lib/api/type-contracts/research-delivery.ts` for market intelligence, tender/product requirements, solution delivery pack, delivery quality, architecture readiness, and architect workbench contracts.
- Added `src/lib/api/type-contracts/research-workspace.ts` for tracking topics, report versions, timelines, compare snapshots, markdown archives, entity details, workspace, and topic refresh contracts.
- Added `src/lib/api/type-contracts/research-watchlists.ts` for watchlists, run-due responses, run history, digest exports, ops summaries, and automation status contracts.
- Added `src/lib/api/type-contracts/research-evaluation.ts` for low-quality review queue, offline evaluation, follow-up delta evaluation, delivery export diagnostics, and golden evaluation contracts.
- Added `src/lib/api/type-contracts/research-experiments.ts` for experiment lanes, control plane, gates, rollout manifests, active policies, runtime snapshots, effective config, and orchestration plans.
- Added `src/lib/api/type-contracts/research-retrieval.ts` for section evidence packs, section retrieval packs, retrieval index rebuild/status, and retrieval search result contracts.
- Kept `src/lib/api/types.ts` and `src/lib/api/type-contracts/research.ts` as stable public re-export paths so feature clients and UI imports do not churn.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new research DTO owner rows and refreshed hotspot guidance.

Module boundary decision:

- The public API type import path remains stable; the split is an internal ownership change for maintainability.
- Report DTOs are still one cohesive file because source diagnostics, entity evidence, readiness, quality, and follow-up diagnostics all compose into `ApiResearchReport`.
- Delivery, workspace, watchlist, evaluation, experiment, and retrieval DTOs now follow their feature-client and backend-domain boundaries.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-report.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-delivery.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-workspace.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-watchlists.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-evaluation.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-experiments.ts`
- `git diff --no-index --check /dev/null src/lib/api/type-contracts/research-retrieval.ts`

### 2026-05-31: Research Center Controller Domain Hook Split Slice 33

Scope:

- Extracted experiment/control-plane, follow-up diagnostics, delivery diagnostics, experiment plan actions, and retrieval-index rebuild/status orchestration into `src/components/research/use-research-center-experiment-controller.ts`.
- Extracted markdown archive filter/sort state, delivery digest derivation, download, and deletion actions into `src/components/research/use-research-center-archive-controller.ts`.
- Extracted workspace loading, saved views, tracking topics, compare snapshots, topic refresh, and apply/save/delete actions into `src/components/research/use-research-center-workspace-controller.ts`.
- Extracted watchlist loading, automation status, ops summaries, digest export, run history, due-run orchestration, schedule/status updates, refresh actions, and copy commands into `src/components/research/use-research-center-watchlist-controller.ts`.
- Added shared `triggerMarkdownDownload` support to `src/components/research/research-center-utils.ts` for archive and digest downloads.
- Reduced `src/components/research/use-research-center-controller.ts` from 1,437 to 670 lines; it now aggregates filter/source/Daily Brief/low-quality/report-card state and section prop bundles.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new Research Center controller ownership rows and refreshed hotspot guidance.

Module boundary decision:

- The public `useResearchCenterController` hook remains the stable page-level composition API for existing section components.
- Experiment, archive, workspace, and watchlist hooks now own their own loading, mutation, message/error state, and derived action props.
- The parent controller should only coordinate cross-domain filter state, source settings, Daily Brief, low-quality review, report-card loading, and final section prop bundle assembly until those domains justify their own slices.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-experiment-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-archive-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-workspace-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-watchlist-controller.ts`

### 2026-05-31: Research Center Residual Controller Split Slice 34

Scope:

- Extracted public-source settings loading, default fallback, connector status error handling, and source toggle persistence into `src/components/research/use-research-center-source-settings-controller.ts`.
- Extracted Daily Brief loading, refresh action, refresh/loading flags, and brief error state into `src/components/research/use-research-center-daily-brief-controller.ts`.
- Extracted research report/action-card knowledge entry loading, query/focus scoped refresh, normalized card state, loading state, and load errors into `src/components/research/use-research-center-cards-controller.ts`.
- Extracted low-quality review queue loading, rewrite/accept/revert actions, queue refresh, action state, messages, and dependent evaluation/report refresh callbacks into `src/components/research/use-research-center-low-quality-controller.ts`.
- Reduced `src/components/research/use-research-center-controller.ts` from 670 to 415 lines; it now owns filter/facet/view derivation, cross-section href builders, and section prop bundle assembly.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new residual controller owners and refreshed hotspot guidance.

Module boundary decision:

- The Research Center aggregation hook should stay as the stable page-level API and avoid owning fetch/mutation side effects.
- Source settings, Daily Brief, cards, and low-quality review now match the existing experiment/archive/workspace/watchlist controller pattern.
- The next Research Center split should target derived filter/facet/view-state helpers only if the aggregation hook grows again.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-source-settings-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-daily-brief-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-cards-controller.ts`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-low-quality-controller.ts`

### 2026-05-31: Research Center Derived View Model Split Slice 35

Scope:

- Extracted sorted/visible item derivation from `src/components/research/use-research-center-controller.ts` into `src/components/research/use-research-center-view-model.ts`.
- Moved region, industry, and action-type facet option derivation into the view-model hook.
- Moved filter meta, perspective meta, overview stats, retrieval-lens counts, active perspective, and active filter labels into the view-model hook.
- Reduced `src/components/research/use-research-center-controller.ts` from 415 to 282 lines; it now owns filter state, controller composition, cross-section href builders, and section prop bundle assembly.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new Research Center view-model owner row and refreshed hotspot guidance.

Module boundary decision:

- Pure derived UI state now belongs in `use-research-center-view-model.ts`; the controller should not carry sorting/filtering/counting policy.
- `useResearchCenterController` remains the public page-level composition API so section prop imports stay stable.
- Future Research Center work should only split the controller again if new cross-section domains are added; simple display derivations should go to the view model.

Verified:

- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/research/use-research-center-view-model.ts`

### 2026-05-31: Report Card View Model, Collector Ops Controllers, and Research Workflow Facade Slice 36

Scope:

- Extracted `research-report-card.tsx` quality/readiness/profile/source diagnostic derivations into `src/components/inbox/research-report-card-view-model.ts`.
- Reduced `src/components/inbox/research-report-card.tsx` from 909 to 615 lines; it now focuses on report-card presentation composition.
- Extracted Collector Ops route/source/OCR batch metrics into `src/components/settings/use-collector-ops-route-metrics.ts`.
- Split Collector Ops action orchestration into `use-collector-ops-general-actions.ts`, `use-collector-ops-daemon-actions.ts`, `use-collector-ops-wechat-agent-actions.ts`, and `use-collector-ops-wechat-agent-config.ts`.
- Reduced `src/components/settings/use-collector-ops-panel-controller.ts` from 677 to 210 lines; it now owns status aggregation, polling, and controller composition.
- Moved the Collector Ops localization map into `src/components/settings/collector-ops-panel-copy.ts` as a module-level constant and reduced `collector-ops-panel.tsx` from 982 to 30 lines.
- Converted `generate_research_report` in `backend/app/services/research_service.py` into a thin setup facade that delegates to `_run_research_generation_workflow`, keeping this slice at workflow-spine level and avoiding new helper-cluster churn.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new frontend controller/view-model owners and refreshed `research_service.py` risk notes.

Module boundary decision:

- Report-card derived state belongs in a pure view-model helper; presentation sections should consume already-normalized metadata.
- Collector Ops controller should compose domain action/config hooks instead of directly owning source/import/OCR/general operation mutations.
- Collector Ops copy is not rendering or behavior; keeping it isolated prevents the settings page shell from regrowing.
- `research_service.py` keeps compatibility wrappers and setup binding for now; the next backend step should move the workflow spine into an application workflow module only after caller seams are stable.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py`
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null src/components/inbox/research-report-card-view-model.ts`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-route-metrics.ts`
- `git diff --no-index --check /dev/null src/components/settings/collector-ops-panel-copy.ts`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-general-actions.ts`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-daemon-actions.ts`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-wechat-agent-actions.ts`
- `git diff --no-index --check /dev/null src/components/settings/use-collector-ops-wechat-agent-config.ts`

### 2026-05-31: Research Workflow Module and Token Migration Slice 37

Scope:

- Moved the research generation workflow spine from `backend/app/services/research_service.py` into `backend/app/services/research/generation_workflow.py`.
- Added `ResearchGenerationWorkflowDependencies` so the new workflow module receives the existing compatibility wrappers from `research_service.py`; this preserves endpoint/test monkeypatch seams while moving the application workflow out of the facade.
- Reduced `backend/app/services/research_service.py` from 8,976 to 8,504 lines; the new workflow module is 755 lines.
- Kept `generate_research_report` as the public facade that prepares setup and wires workflow dependencies.
- Migrated the report card parent shell, summary panels, follow-up impact surfaces, quality-profile panels, and action message color to semantic `--af-*` theme tokens.
- Migrated Collector Ops panel description, stat cards, general operations cards, daemon/source-health/log surfaces, WeChat batch cards, preview/log/config surfaces, and progress fill away from hard-coded white/slate day-mode classes.
- Updated `docs/module-ownership-map-2026-05-21.md` to record the new workflow owner and revised frontend token ownership/risk notes.

Module boundary decision:

- `generation_workflow.py` is the application workflow owner; domain logic still belongs in the already extracted research submodules.
- `research_service.py` remains the compatibility/dependency wiring layer until direct callers and monkeypatch seams can be narrowed.
- Report card and Collector Ops should keep using semantic tokens at the shell/panel level before migrating the remaining downstream report subcomponents.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/generation_workflow.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py backend/tests/test_architecture_boundaries.py` (`7 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null backend/app/services/research/generation_workflow.py`

### 2026-05-31: Workflow Dependency Port and Report Section Token Slice 38

Scope:

- Replaced the flat `ResearchGenerationWorkflowDependencies` field list with stage-level dependency ports in `backend/app/services/research/generation_workflow.py`: progress, source collection, scope, enrichment, generation, ranking, assembly, and quality.
- Kept `research_service.py` as the compatibility seam by wiring those stage ports from the existing monkeypatch-friendly wrappers instead of importing domain functions directly into the workflow.
- Added semantic danger/status helper classes in `src/app/globals.css`.
- Migrated report-card downstream sections away from hard-coded Tailwind status palettes: delivery, diagnostics/source groups, strategic panels, readiness/playbook, insights, review queue, and appendix now use semantic `--af-*` status tokens or shared chip classes.
- Updated the ownership map to reflect that `generation_workflow.py` no longer exposes a giant flat injection surface and that report-section token drift is no longer the main report-card risk.

Module boundary decision:

- The workflow module should depend on stage ports, not dozens of individual callbacks. This keeps the application workflow testable while making dependency ownership legible.
- Compatibility wrappers remain in `research_service.py` until endpoint callers and tests stop relying on direct monkeypatch seams.
- Report-card subcomponents should use semantic state tokens (`success`, `warning`, `danger`, `info`) rather than encoding day-mode status colors in each component.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/generation_workflow.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py backend/tests/test_architecture_boundaries.py` (`7 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for the new workflow/docs/report-section files touched in this slice

### 2026-06-01: Collector Ops Token Closure Slice 39

Scope:

- Replaced the remaining Collector Ops daemon coverage color helper in `src/components/settings/collector-ops-panel-utils.ts` with semantic chip/status token classes.
- Verified that `collector-ops-*` components and hooks no longer emit hard-coded Tailwind status palettes such as `emerald`, `amber`, `rose`, `sky`, `blue`, `cyan`, `indigo`, `fuchsia`, `slate`, or `white`.
- Updated the ownership map so Collector Ops token migration is no longer listed as a remaining next slice.

Module boundary decision:

- Collector Ops presentation sections should consume shared semantic status classes from `globals.css`; route/daemon health helpers should return semantic intent classes, not concrete day-mode color palettes.

Verified:

- `rg -n "bg-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|text-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|border-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|hover:text-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|bg-white|border-white" src/components/settings/collector-ops-*.tsx src/components/settings/use-collector-ops-*.ts src/components/settings/collector-ops-panel*.ts src/components/settings/collector-ops-panel.tsx` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and Collector Ops utility files touched in this slice

### 2026-06-01: Research Center Tone Utility Token Slice 40

Scope:

- Migrated centralized Research Center status helpers in `src/components/research/research-center-utils.ts` from concrete Tailwind palettes to semantic chip/panel/text token classes.
- Migrated topic workspace utility tones in `src/components/research/research-topic-workspace-utils.ts`, including quality, timeline event, entity value bucket, factor support bucket, and follow-up impact tones.
- Reduced status-tone drift across Research Center results, low-quality review, experiment control, watchlist, workspace, topic timeline, topic compare, and topic workspace surfaces without changing their request/state controllers.

Module boundary decision:

- Research Center section components should consume semantic tone helpers from utility modules instead of carrying status palettes per section.
- Remaining token work should focus on section surface/text classes, not status badge helper logic.

Verified:

- `rg -n "bg-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|text-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)|border-(sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|slate)" src/components/research/research-center-utils.ts src/components/research/research-topic-workspace-utils.ts` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and Research Center utility files touched in this slice

### 2026-06-01: Research Center Section Surface Token Slice 41

Scope:

- Migrated `src/components/research/research-center-sidebar-controls.tsx` from hard-coded white/slate/sky/rose surface and text classes to semantic `--af-*` surface, border, text, danger, and info tokens.
- Migrated `src/components/research/research-center-source-settings-section.tsx` to semantic surface/text tokens and shared state chips for connector/source status.
- Migrated `src/components/research/research-center-experiment-control-section.tsx` surface/text/status classes to semantic tokens, keeping its experiment, retrieval, runtime, gate, and export controller wiring unchanged.
- Verified the three targeted sections no longer contain hard-coded Tailwind light/status palette classes for `white`, `slate`, `sky`, `amber`, `emerald`, `rose`, or adjacent status color families.

Module boundary decision:

- Research Center presentation sections should own layout only; visual meaning should flow through semantic theme tokens and shared state chip/panel classes.
- `research-center-experiment-control-section.tsx` remains large, but this slice intentionally avoids component splitting so the token migration stays visually scoped.

Verified:

- `rg -n "bg-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow)|text-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow)|border-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow)|hover:(bg|text|border)-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow)|placeholder:text-(slate|gray|zinc)" src/components/research/research-center-sidebar-controls.tsx src/components/research/research-center-source-settings-section.tsx src/components/research/research-center-experiment-control-section.tsx` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and the three targeted Research Center section files

### 2026-06-01: Research Center Remaining Section Token Slice 42

Scope:

- Migrated `src/components/research/research-center-results-section.tsx` report/action cards, diagnostics, ranked previews, and action-card subpanels from hard-coded white/slate/status palettes to semantic `--af-*`, `af-chip`, and `af-state-panel-*` classes.
- Migrated `src/components/research/research-center-watchlist-section.tsx` automation health, run history, command panels, digest export, failed samples, and per-watchlist cards to semantic surface/text/status tokens.
- Migrated `src/components/research/research-center-workspace-sections.tsx` compare snapshots, saved views, tracking-topic cards, new-entity chips, and topic-version history to semantic tokens.
- Migrated `src/components/research/research-center-markdown-archives-section.tsx` archive controls, archive cards, follow-up impact panel, archive-kind chips, and linked workspace chips to semantic tokens.
- Closed the smaller leftover `src/components/research/research-center-low-quality-review-section.tsx` token gap so the Research Center section set no longer carries hard-coded day-mode palette classes.
- Updated `src/lib/research-archive-metadata.ts` archive delivery metric tone helper to return semantic chip classes.

Module boundary decision:

- Research Center section components should remain presentation-only; theme intent belongs to shared semantic token classes and tone helpers rather than duplicated Tailwind color palettes.
- Archive delivery metric tone is shared metadata presentation policy, so it should emit semantic chip intent and stay independent from concrete light/dark palette choices.

Verified:

- `rg -n "bg-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|text-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|border-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|hover:(bg|text|border)-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|placeholder:text-(slate|gray|zinc)" src/components/research/research-center-*.tsx src/components/research/research-center-utils.ts src/lib/research-archive-metadata.ts` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs, Research Center section files, and archive metadata helper touched in this slice

### 2026-06-01: Research Archive and Console Token Slice 43

Scope:

- Migrated `src/components/research/research-console-panel.tsx` conversation list, message bubbles, empty/error states, progress timeline, topic filter input, and suggested follow-up chips to semantic theme tokens.
- Migrated `src/components/research/research-archive-section-link-popover.tsx` popover shell, loading/error states, section link cards, and retry affordance to semantic theme tokens.
- Migrated `src/components/research/research-markdown-archive-viewer.tsx` archive kind/status helpers, markdown preview typography, metadata chips, delivery digest cards, follow-up/quality/section diagnostics, compare summary, section diff cards, success/error panels, and code blocks to semantic tokens.
- Verified the targeted research archive/console files no longer contain hard-coded Tailwind light/status palette classes for `white`, `slate`, `sky`, `amber`, `emerald`, `rose`, or adjacent status color families.

Module boundary decision:

- Research archive preview and console panels are research-domain presentation surfaces; they should keep business rendering local while delegating visual intent to semantic tokens and shared status classes.
- Archive comparison highlighting now uses semantic border/surface/shadow tokens instead of embedded blue-tinted day-mode shadows.

Verified:

- `rg -n "bg-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|text-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|border-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|hover:(bg|text|border)-(white|slate|gray|zinc|stone|sky|amber|emerald|rose|violet|blue|cyan|indigo|fuchsia|purple|red|green|yellow|orange)|placeholder:text-(slate|gray|zinc)|decoration-(sky|rose|emerald|amber|slate)|shadow-\\[0_0_0_4px_rgba" src/components/research/research-console-panel.tsx src/components/research/research-archive-section-link-popover.tsx src/components/research/research-markdown-archive-viewer.tsx` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and research archive/console files touched in this slice

### 2026-06-01: Research Compare and Topic Version Token Slice 44

Scope:

- Migrated `src/components/research/research-compare-matrix.tsx` snapshot headers, diff panels, section diagnostics, quality review cards, filter controls, entity comparison rows, evidence links, and saved-snapshot affordances from hard-coded white/slate/status palettes to semantic `--af-*`, `af-chip`, and `af-state-panel-*` classes.
- Migrated `src/components/research/research-topic-version-compare-section.tsx` side-by-side version panels, follow-up impact cards, candidate-profile chips, diff highlights, field-diff rows, score panels, and source-contribution cards to semantic surface/text/status tokens.
- Confirmed the topic workspace compare tone helpers already return semantic chip classes, so the version-compare section does not reintroduce hard-coded status palettes through helper outputs.
- Replaced remaining day-mode-only compare hover/shadow classes with semantic hover surface and shared `af` shadow tokens.

Module boundary decision:

- Research compare matrix and topic-version compare remain focused presentation sections; data derivation stays in their existing controllers/utilities while visual intent is centralized in semantic theme tokens.
- Compare/topic workspace is now considered closed for the current theme-token migration line unless new UI grows enough to justify structural section splitting.

Verified:

- `rg -n "hover:bg-white|rgba\\(|shadow-\\[0_|bg-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|text-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|border-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-" src/components/research/research-compare-matrix.tsx src/components/research/research-topic-version-compare-section.tsx` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and compare/topic version files touched in this slice

### 2026-06-01: Knowledge and Session Summary Token Slice 45

Scope:

- Migrated `src/components/knowledge/knowledge-detail-card.tsx` quality/readiness tone helpers, ranked panels, report diagnostics, commercial summary, review queue, related entries, inline stage cards, and research-detail surfaces from hard-coded white/slate/status palettes to semantic `--af-*`, `af-chip`, `af-state-panel-*`, and shared shadow tokens.
- Migrated `src/components/session/session-summary-panel.tsx` collector batch snapshot, latest item filters/cards, research recommendation cards, action-plan metadata, watchlist priority cards, prompt export surfaces, and focused summary helper panels to semantic theme tokens.
- Replaced the last Collector Ops presentation hard-coded item-card shadow in `src/components/settings/collector-ops-wechat-agent-batch-section.tsx` with `--af-shadow-card`.
- Removed day-mode-only inline CSS gradients/rgba colors from the knowledge detail stage styling and rebound them to semantic surface, border, text, and shadow variables.

Module boundary decision:

- Knowledge detail and session summary remain large presentation surfaces; this slice deliberately limits changes to theme semantics and does not mix in structural component extraction.
- Collector Ops presentation is now token-clean for the current targeted scan; remaining Collector Ops risk is copy-map breadth and command-controller growth rather than day-mode styling.

Verified:

- `rg -n "bg-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|text-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|border-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|hover:(bg|text|border)-(white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-|placeholder:text-(slate|gray|zinc)|shadow-\\[0_|rgba\\(|from-(sky|blue|cyan|emerald|amber|rose|slate)-|via-(sky|blue|cyan|emerald|amber|rose|slate)-|to-(sky|blue|cyan|emerald|amber|rose|slate)-|rgb\\(" src/components/knowledge/knowledge-detail-card.tsx src/components/session/session-summary-panel.tsx src/components/settings/collector-ops-*.tsx` returns no matches.
- `npm run lint`
- `npm run build`
- `git diff --check`
- `git diff --no-index --check /dev/null ...` for docs and tokenized knowledge/session/Collector Ops files touched in this slice

### 2026-06-01: UI Baseline Realignment and Research Runtime Recovery Slice 46

Scope:

- Compared the current global theme against the earlier Git tags, with `v0.8.0+20260518` representing the preferred translucent day UI baseline.
- Realigned `src/app/globals.css` semantic tokens to the earlier light style: pale blue page gradients, `#3370ff` accent, translucent white surfaces, glass topbar/nav controls, and softer Apple-style shadows.
- Reworked dark mode as a matching companion to the earlier day UI rather than a separate heavy blue design: deep neutral page gradient, translucent dark surfaces, low-saturation cyan accent, and the same glass material rules.
- Installed the screenshot-referenced Taste Skill from `github.com/Leonxlnx/taste-skill` via git fallback after the Python download path hit a local certificate verification error.
- Recovered the local research runtime by starting the FastAPI backend on `localhost:8000`; the frontend research error was caused by the backend service being down, not by the research card UI.

Module boundary decision:

- This slice intentionally adjusts only global theme primitives. Product surfaces continue to consume semantic tokens, so day/night visual direction can change without re-editing each feature panel.
- Research availability for local review depends on both frontend and backend runtimes; Safari testing should keep `localhost:3012` frontend and `localhost:8000` backend running together.

Verified:

- `npm run lint`
- `npm run build`
- Frontend smoke: `/`, `/inbox`, `/research`, `/settings`, `/knowledge`, `/session-summary` on `localhost:3012` returned 200.
- Backend smoke: `/healthz` and `/api/research/source-settings` on `localhost:8000` returned 200.
- Research job smoke: `POST /api/research/jobs` returned a queued job and progressed without immediate error.
- `git diff --check`

### 2026-06-05: Section Delivery Dependency Seam Migration Slice 50

Scope:

- Replaced `test_research_section_retrieval_service.py` facade private dependency providers with deterministic test-local `DeliveryEnrichmentDependencies` and `FollowupDiagnosticsDependencies`.
- Removed all `research_service._*` private seam usage from `backend/tests/test_research_section_retrieval_service.py`.
- Kept quality expansion dependency seam migration for a later slice because it spans public search, source refinement, report rebuild, entity ranking, diagnostics, evaluation, and delivery regeneration.

Module boundary decision:

- Section delivery tests should validate owner modules with explicit dependencies instead of using the facade as a dependency factory.
- Broad quality-expansion dependency seams should be migrated only after narrower owner-level dependency builders or smaller test doubles exist; replacing the whole pipeline with ad-hoc stubs would reduce test value.

Verified:

- `python3 -m py_compile backend/tests/test_research_section_retrieval_service.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_section_retrieval_service.py` (`7 passed`)

### 2026-06-05: Research Source Document and Section Delivery Wrapper Migration Slice 49

Scope:

- Moved source text noise filtering, source text analysis cleanup, and `SourceDocument` text assembly from `backend/app/services/research_service.py` to `backend/app/services/research/source_documents.py`.
- Added `render_section_retrieval_prompt_context` to `backend/app/services/research_section_retrieval_service.py`, leaving `research_service.py` as a compatibility wrapper.
- Migrated source-document and section-delivery regression tests from direct `research_service._report_sources_to_source_documents`, `_source_text`, `_render_section_retrieval_prompt_context`, `_enrich_report_for_delivery`, `_render_followup_section_focus_prompt_context`, and `_expand_report_public_sources_until_quality_improves` calls to owner modules.
- Reduced `backend/app/services/research_service.py` from 8,102 to 7,913 lines while preserving API and generation workflow compatibility seams.

Module boundary decision:

- Source document text cleanup belongs with `SourceDocument` conversion and DTO utilities, not the generation facade.
- Section retrieval prompt rendering belongs with section retrieval packs because it is a deterministic projection of retrieval-pack evidence.
- Delivery enrichment and quality expansion tests can call owner modules directly while still using existing dependency providers for monkeypatch-compatible seams.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/source_documents.py backend/app/services/research_section_retrieval_service.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py` (`23 passed`)
- No remaining direct test calls to the migrated source-document and section-delivery wrapper set.

### 2026-06-05: Miniapp Secret Exposure Remediation Slice 48

Scope:

- Replaced the tracked WeChat Mini Program AppID in `miniapp/project.config.json` with `touristappid`.
- Stopped tracking `miniapp/project.private.config.json` and added `miniapp/project.private.config.example.json` for local DevTools setup.
- Updated miniapp docs to require real AppID values only in ignored local config.
- Added `scripts/secret_scan.py` plus `npm run security:scan`, `npm run security:scan:history`, and `npm run security:scan:local`.

Security decision:

- Current syncable files must not contain real AppIDs, API keys, tokens, passwords, private-key blocks, or common cloud credentials.
- Ignored local files may still contain operational credentials, but `npm run security:scan:local` reports them with masked values so they can be rotated or scrubbed before packaging a public artifact.
- Existing public GitHub/ModelScope history still contains the old WeChat AppID references. Fully removing those from remote history requires an explicit history-rewrite and force-push decision across both remotes.

Verified:

- `npm run security:scan` (`No likely secrets found.`)
- `npm run security:scan:local` reported only ignored local credentials in `backend/.env` and local `miniapp/project.private.config.json`, with masked values.
- `npm run security:scan:history` reported historical masked WeChat AppID references, confirming why GitHub still has an open secret scanning alert.

### 2026-06-05: Research Facade Wrapper Retirement Slice 47

Scope:

- Retired the first zero-call legacy private wrapper batch from `backend/app/services/research_service.py`, covering unused query/scope, tender-detail, entity graph, field sanitization, section-quality, runtime-config, follow-up, archive-context, stored-entity, and guarded-rewrite facade helpers.
- Moved tender-detail query-plan regression coverage from `research_service._build_tender_detail_query_plan` to `backend/app/services/research/tender_detail_enrichment.py`'s owned `build_tender_detail_query_plan` entrypoint.
- Moved source query-plan regression coverage in `backend/tests/test_research_hybrid_retrieval.py` and `backend/tests/test_research_archive_context.py` from `research_service._build_query_plan`, `_build_expanded_query_plan`, `_build_corrective_query_plan`, and `_build_company_profile_query_plan` to `backend/app/services/research/source_query_plans.py` owner functions.
- Reduced `backend/app/services/research_service.py` from 8,528 to 8,102 lines without changing API route behavior or the public `generate_research_report` entrypoint.

Module boundary decision:

- This slice deletes only wrappers with no production or test callers, plus migrates test-facing wrapper assertions whose owner modules already expose stable entrypoints.
- Stage-port dependency wiring remains in `research_service.py` for now; direct monkeypatch seams should be retired incrementally by moving tests to owner modules before deleting more wrappers.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_hybrid_retrieval.py` (`17 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py` (`5 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_archive_context.py backend/tests/test_architecture_boundaries.py` (`47 passed`)

### 2026-05-25: Research Stored Rewrite, Ranking, and Action Delivery Slice 23

Scope:

- Extracted full stored-report rewrite orchestration from `backend/app/services/research_service.py` into `backend/app/services/research/stored_report_rewrite.py`, including guarded backlog report assembly and post-rewrite low-signal fallback.
- Extracted report readiness scoring and low-signal execution guard policy into `backend/app/services/research/report_readiness.py`.
- Extracted research action-card construction into `backend/app/services/research/action_cards.py`, including card evidence formatting, buyer-entry, differentiation, project-timing, visit-sequence, ecosystem, and two-week execution cards.
- Moved entity ranking heuristics, ranked-entity reasoning, candidate-profile support scoring, and pending-candidate promotion into `backend/app/services/research/entity_ranking.py`.
- Kept compatibility wrappers in `research_service.py` for API callers and direct tests while reducing it from 12,065 to 10,047 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with stored rewrite, readiness, action-card, entity-ranking, and new hotspot ownership notes.

Module boundary decision:

- Stored-report rewrite is persisted-report orchestration and now owns its guarded rewrite path outside the main generation workflow.
- Readiness is delivery gate policy; action cards are delivery artifacts. Both should be built by delivery-domain modules instead of remaining in the report workflow hub.
- Entity ranking heuristics and candidate support scoring belong with the ranking domain service, while `research_service.py` only adapts existing monkeypatch seams through narrow wrappers.
- Remaining research-service risk is now narrower: stored-report entity canonicalization helpers, commercial summary, technical appendix/review queue, follow-up diagnostics, and section confidence/scoring helpers.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/*.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_research_low_quality_audit.py backend/tests/test_architecture_boundaries.py` (`49 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_research_low_quality_audit.py backend/tests/test_architecture_boundaries.py` (`117 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-25: Research Entity, Scope, Query, and Stored Rewrite Helpers Slice 22

Scope:

- Extracted source query plan construction from `backend/app/services/research_service.py` into `backend/app/services/research/source_query_plans.py`, covering base, scoped official, corrective, expanded, and company profile/contact/team query plans.
- Extracted scope-term helpers into `backend/app/services/research/scope_terms.py`, covering keyword/focus cleanup, explicit exclusions, topic/company anchors, resolved company terms, and theme-term construction.
- Extracted report field sanitization into `backend/app/services/research/report_field_sanitization.py`, preserving field-level validity checks, entity normalization, generic row filtering, and canonical deduplication.
- Extracted entity graph construction into `backend/app/services/research/entity_graph_builder.py`, covering role inference, alias aggregation, source-tier counts, evidence links, and graph lookup support.
- Extracted stored-report rewrite guard/support helpers into `backend/app/services/research/stored_report_rewrite.py`, covering low-signal source checks, concrete target support, guarded diagnostics, rewrite-mode assessment, and guarded title generation.
- Kept compatibility wrappers in `research_service.py` for direct tests/monkeypatch seams while reducing it from 12,993 to 12,065 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new query-plan, scope-term, field-sanitization, entity-graph, and stored-rewrite helper owners.

Module boundary decision:

- Query planning is source acquisition policy and should be reusable by evidence, corrective, company, and candidate-profile enrichment without living in the orchestration service.
- Scope terms are lexical normalization policy; scope inference can keep using the legacy wrapper while no longer owning token cleanup and anchor resolution inline.
- Report field sanitization is DTO hygiene and should be isolated from source extraction and final report assembly.
- Entity graph construction is a reusable evidence projection over sources and should not stay embedded in the report workflow hub.
- Stored-report rewrite still has orchestration in `research_service.py`, but guard assessment and support checks now live in a dedicated rewrite helper module.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/*.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_section_retrieval_service.py` (`45 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`115 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-25: Research Long-tail Helper Split Slice 21

Scope:

- Extracted strategy scope planning, topic-specific overrides, and strategy LLM refinement from `backend/app/services/research_service.py` into `backend/app/services/research/strategy_refinement.py`.
- Extracted source theme/scope scoring, company-anchor filtering, recency filtering, report-source refinement, and region-conflict signatures into `backend/app/services/research/source_scope_policy.py`.
- Extracted organization, key people, department, and public-contact row extraction utilities into `backend/app/services/research/ranking_source_utility.py`.
- Extracted pre-generation orchestration setup into `backend/app/services/research/generation_setup.py`, covering settings/LLM/runtime, follow-up diagnostics, strategy scope planning, source settings, and archive context assembly.
- Kept compatibility wrappers in `research_service.py` for tests and monkeypatch seams while reducing it from 13,428 to 12,993 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new strategy refinement, source scoping, ranking/source utility, and generation setup owners.

Module boundary decision:

- Strategy refinement is post-processing and planning policy; it should be callable by generation execution without embedding prompt repair logic in the main orchestration service.
- Source scoping policy owns source relevance filtering and scoring, while `research_service.py` keeps narrow wrappers for existing direct callers.
- Ranking/source utility owns source-derived row extraction, separate from entity ranking DTO assembly and final report assembly.
- Generation setup is the initialization phase before source collection; the main `generate_research_report` function should start from a prepared context instead of assembling settings, follow-up scope, runtime, and archive context inline.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/*.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_section_retrieval_service.py` (`45 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`115 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Research Generation, Evidence, Tender, and Diagnostics Split Slice 20

Scope:

- Extracted source diagnostics construction from `backend/app/services/research_service.py` into `backend/app/services/research/source_diagnostics.py`.
- Extracted tender-detail enrichment from `research_service.py` into `backend/app/services/research/tender_detail_enrichment.py`, preserving `_build_tender_detail_query_plan` compatibility.
- Extracted general weak-evidence expansion from `research_service.py` into `backend/app/services/research/evidence_expansion.py`.
- Extracted final generation execution from `research_service.py` into `backend/app/services/research/generation_execution.py`.
- Extracted source-derived intelligence row construction from `research_service.py` into `backend/app/services/research/source_intelligence.py`, preserving `_build_source_intelligence` monkeypatch compatibility.
- Reduced `backend/app/services/research_service.py` from 14,046 to 13,428 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new generation/evidence/tender/diagnostics/source-intelligence owners and new hotspot baseline.

Module boundary decision:

- Source diagnostics is report metadata construction and should stay separate from generation orchestration.
- Tender-detail enrichment is a narrow evidence expansion lane triggered by confirmed tender sources, not general report generation.
- General evidence expansion owns weak-evidence detection and source refresh before corrective expansion.
- Final generation execution owns LLM prompt execution and result parsing/refinement, while `research_service.py` owns high-level orchestration.
- Source intelligence is a source-derived business-intelligence projection and should be reusable by expansion/enrichment modules through the compatibility wrapper.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/source_intelligence.py backend/app/services/research/generation_execution.py backend/app/services/research/evidence_expansion.py backend/app/services/research/tender_detail_enrichment.py backend/app/services/research/source_diagnostics.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_section_retrieval_service.py` (`45 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`115 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Research Enrichment and Expansion Split Slice 19

Scope:

- Extracted company/source enrichment from `backend/app/services/research_service.py` into `backend/app/services/research/company_source_enrichment.py`.
- Extracted corrective expansion from `research_service.py` into `backend/app/services/research/corrective_expansion.py`.
- Extracted candidate-profile enrichment from `research_service.py` into `backend/app/services/research/candidate_profile_enrichment.py`.
- Extracted quality-triggered public-source expansion from `research_service.py` into `backend/app/services/research/quality_expansion.py`.
- Extracted delivery enrichment and readiness guardrails from `research_service.py` into `backend/app/services/research/delivery_enrichment.py`.
- Kept compatibility wrappers in `research_service.py` for existing tests and monkeypatch seams, while reducing it from 14,717 to 14,046 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new research enrichment/expansion owners and the new hotspot baseline.

Module boundary decision:

- Company/source enrichment owns profile/contact search planning, official source fallback, enriched source merge/refine, and source-intelligence refresh.
- Corrective expansion owns low-quality retrieval detection, corrective query construction, corrective source collection, and retrieval-correction profile refresh.
- Candidate-profile enrichment owns candidate company profile/contact/team evidence collection and reranking refresh after profile sources are added.
- Quality expansion owns self-evaluation-triggered public-source expansion and report rebuild after additional evidence is collected.
- Delivery enrichment owns post-generation report packaging: readiness, commercial summary, appendix/review queue, runtime retrieval packs, market/delivery packs, and readiness guardrails.

Verified:

- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/company_source_enrichment.py backend/app/services/research/corrective_expansion.py backend/app/services/research/candidate_profile_enrichment.py backend/app/services/research/quality_expansion.py backend/app/services/research/delivery_enrichment.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_section_retrieval_service.py` (`45 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`115 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Research Source/Ranking/Assembly Split and Collector Facade Removal Slice 18

Scope:

- Deleted `backend/app/api/collector.py` after moving internal tests and `main.py` off the legacy collector facade.
- Verified collector public paths are still registered through owned modules: browser/plugin/URL ingest, OCR, operations, WeChat Favorites, and URL resolve.
- Extracted initial adapter/public-web collection and source extraction/filtering from `backend/app/services/research_service.py` into `backend/app/services/research/source_collection.py`.
- Extracted target account, competitor, and ecosystem-partner ranking set construction plus candidate-profile promotion into `backend/app/services/research/entity_ranking.py`.
- Extracted final `ResearchReportResponse` assembly into `backend/app/services/research/report_assembly.py`.
- Reused the ranking module in quality-expansion rebuild and stored-report rewrite paths to reduce repeated entity-ranking logic.
- Reduced `backend/app/services/research_service.py` from 14,905 to 14,717 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` to remove the collector facade row and add source collection, entity ranking, and final report assembly owners.

Module boundary decision:

- Collector route ownership is now fully explicit: there is no fallback collector router or compatibility facade in the repo.
- Initial source collection is retrieval orchestration, not report generation; generation now consumes the collected sources and diagnostics.
- Target/competitor/partner ranking is reusable entity-evidence logic and should be constructed through a ranking-set value object.
- Final report DTO assembly is serialization/materialization work and should be kept outside the main research orchestration function.

Verified:

- `python3 -m py_compile backend/app/main.py backend/app/api/research.py backend/app/services/research_service.py backend/app/services/research/source_collection.py backend/app/services/research/entity_ranking.py backend/app/services/research/report_assembly.py backend/app/services/research/generation_artifacts.py backend/app/services/research/retrieval_orchestration.py backend/app/services/research/report_persistence.py`
- `.venv311/bin/python` route registry check for collector browser/plugin/URL/OCR/operations/Favorites/URL-resolve endpoints
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`63 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_architecture_boundaries.py` (`108 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Collector Legacy Facade and Research Generation/Retrieval Slice 17

Scope:

- Moved remaining collector tests off direct `app.api.collector` imports and onto `collector_ingest`, `collector_ocr_routes`, `collector_ops_serializers`, and `collector_wechat_favorites`.
- Removed the legacy collector router import/include from `backend/app/main.py`; public `/api/collector/...` paths are now registered only by owned route modules.
- Reduced `backend/app/api/collector.py` from 670 lines to a 127-line deprecated compatibility facade with direct re-exports only.
- Extracted research partial outline fallback generation and draft report materialization into `backend/app/services/research/generation_artifacts.py`.
- Extracted runtime section-retrieval prompt orchestration into `backend/app/services/research/retrieval_orchestration.py`.
- Extracted saved research report lookup/upsert persistence into `backend/app/services/research/report_persistence.py` and wired `backend/app/api/research.py` to that service.
- Reduced `backend/app/services/research_service.py` from 15,008 to 14,905 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new generation, retrieval, persistence, and collector compatibility ownership rows.

Module boundary decision:

- `collector.py` is no longer an HTTP router. It exists only as a temporary import-compatibility facade and should be deleted when external direct imports are retired.
- Research draft/outline artifact construction is generation-support logic and should not stay embedded in the main report orchestration function.
- Runtime section retrieval context is retrieval orchestration and now returns an explicit context object consumed by the generation prompt.
- Research report upsert belongs in a persistence service rather than in the HTTP router.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ingest.py backend/app/api/collector_ocr_routes.py backend/app/api/collector_operations.py backend/app/api/collector_wechat_agent.py backend/app/api/collector_wechat_favorites.py backend/app/api/collector_url_resolve.py backend/app/main.py backend/app/api/research.py backend/app/services/research_service.py backend/app/services/research/generation_artifacts.py backend/app/services/research/retrieval_orchestration.py backend/app/services/research/report_persistence.py backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py`
- `.venv311/bin/python` route registry check for collector browser/plugin/URL/OCR/operations/Favorites/URL-resolve endpoints
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_section_retrieval_service.py backend/tests/test_architecture_boundaries.py` (`63 passed`)
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_architecture_boundaries.py` (`108 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Collector Favorites/Resolve and Research Runtime Slice 16

Scope:

- Extracted WeChat Favorites preview, import, batch list/detail, and batch response mapping from `backend/app/api/collector.py` into `backend/app/api/collector_wechat_favorites.py`.
- Extracted URL resolve from `backend/app/api/collector.py` into `backend/app/api/collector_url_resolve.py`.
- Registered both new routers in `backend/app/main.py`, preserving `/api/collector/wechat-favorites/*` and `/api/collector/url/resolve` paths.
- Kept compatibility wrappers in `collector.py` for legacy direct imports while moving `backend/tests/test_multiformat_collector_service.py` Favorites API calls to `collector_wechat_favorites`.
- Reduced `backend/app/api/collector.py` from 860 to 670 lines. At this point it is primarily a compatibility facade plus shared monkeypatch-compatible wrappers.
- Extracted research runtime mode/query-recovery/timeout budget calculation from `backend/app/services/research_service.py` into `backend/app/services/research/runtime_config.py`.
- Kept `research_service.py` compatibility wrappers for `_apply_runtime_query_config` and `_build_research_runtime`, reducing it from 15,043 to 15,008 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with WeChat Favorites, URL resolve, and runtime-config ownership rows plus current hotspot sizes.

Module boundary decision:

- WeChat Favorites import is a collector ingestion subdomain with its own batch response materialization and should not live in the legacy collector facade.
- URL resolve is a narrow adapter around WeChat article URL resolution and belongs in its own route module.
- Runtime budget calculation is generation execution policy; the main research service should consume it through a narrow wrapper rather than owning mode limits and query-recovery overrides inline.
- The next collector slice should focus on retiring compatibility wrappers after more tests/callers are moved to owned modules.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_wechat_favorites.py backend/app/api/collector_url_resolve.py backend/app/main.py backend/tests/test_multiformat_collector_service.py`
- `.venv311/bin/python` route registry check for `/api/collector/wechat-favorites/preview`, `/api/collector/wechat-favorites/import`, `/api/collector/wechat-favorites/batches`, `/api/collector/wechat-favorites/batches/{batch_id}`, and `/api/collector/url/resolve`
- `backend/.venv311/bin/pytest -q backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py`
- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/runtime_config.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_multiformat_collector_service.py`
- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ingest.py backend/app/api/collector_ocr_routes.py backend/app/api/collector_operations.py backend/app/api/collector_wechat_agent.py backend/app/api/collector_wechat_favorites.py backend/app/api/collector_url_resolve.py backend/app/api/collector_external_ingest.py backend/app/api/collector_sources.py backend/app/main.py backend/app/services/research_service.py backend/app/services/research/archive_loader.py backend/app/services/research/archive_context.py backend/app/services/research/runtime_config.py backend/app/services/research/report_storage.py backend/app/services/research/source_documents.py backend/tests/test_multiformat_collector_service.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_architecture_boundaries.py` (`108 passed`)
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Collector Operations and Research Archive Loader Slice 15

Scope:

- Extracted OCR image ingest and OCR preview HTTP entrypoints from `backend/app/api/collector.py` into `backend/app/api/collector_ocr_routes.py`.
- Extracted pending recovery, failed queue, retry, daily summary, ingest attempts, collector status, and collector daemon endpoints into `backend/app/api/collector_operations.py`.
- Extracted WeChat agent status/config/health/self-heal/preview/start-stop/run/batch/dedup endpoints into `backend/app/api/collector_wechat_agent.py`.
- Registered the new OCR, operations, and WeChat agent routers in `backend/app/main.py`, preserving all public `/api/collector/...` paths.
- Kept compatibility wrappers in `collector.py` for direct test/caller imports, including monkeypatchable OCR, daemon, and WeChat preview dependencies.
- Fixed the failed-retry path by making `output_language` an explicit optional parameter instead of relying on an undefined local name.
- Reduced `backend/app/api/collector.py` from 1,299 to 860 lines. The remaining real route ownership is primarily WeChat Favorites import and URL resolve; the rest is compatibility wrappers.
- Extracted stored-report payload parsing, archive report scope hints, archive item construction, and historical candidate loading from `backend/app/services/research_service.py` into `backend/app/services/research/archive_loader.py`.
- Kept `research_service.py` compatibility wrappers for archive tests and generation flow callers, reducing it from 15,177 to 15,043 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with new collector OCR route, operations, WeChat agent, and research archive-loader ownership rows plus current hotspot sizes.

Module boundary decision:

- OCR HTTP routing is separate from OCR heuristics: `collector_ocr_routes.py` owns request/response behavior, while `collector_ocr.py` owns deterministic quality/crop/retry policy.
- Collector operations own queue recovery, status aggregation, retry, daily summaries, and collector daemon control; they should not be mixed with content ingest or WeChat agent automation.
- WeChat agent automation is an integration-control API and now owns its own route module, using shared response serializers instead of keeping command mapping in the legacy router.
- Research archive loading/materialization is persistence/retrieval support logic; generation should consume archive items through the existing wrapper rather than owning SQL loading and stored report materialization inline.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ocr_routes.py backend/app/api/collector_operations.py backend/app/api/collector_wechat_agent.py backend/app/main.py`
- `.venv311/bin/python` route registry checks for OCR, operations/daemon, and WeChat agent endpoints
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_route_quality.py backend/tests/test_wechat_pc_agent_helpers.py`
- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/archive_loader.py backend/app/services/research/archive_context.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_collector_ingest_attempts.py backend/tests/test_wechat_pc_agent_helpers.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py backend/tests/test_architecture_boundaries.py`
- `npm run lint`
- `npm run build`
- `git diff --check`

### 2026-05-24: Collector Browser Ingest and Research Archive Context Slice 14

Scope:

- Extracted browser extraction ingest, browser batch ingest, plugin body ingest, and direct URL ingest from `backend/app/api/collector.py` into `backend/app/api/collector_ingest.py`.
- Registered the new ingest router in `backend/app/main.py`, preserving the existing `/api/collector/browser/ingest`, `/browser/batch-ingest`, `/plugin/ingest`, and `/url/ingest` paths.
- Kept compatibility wrappers in `collector.py` for existing tests and callers that directly import `app.api.collector.ingest_*`, including monkeypatchable `ensure_demo_user`, `_mark_source_collected`, `process_item_in_session`, and `extract_from_browser` seams.
- Reduced `backend/app/api/collector.py` from 1,599 to 1,299 lines after source/feed, external ingest, browser/plugin/URL ingest, OCR helper, and ops response extraction.
- Extracted historical research archive prompt rendering, archive query expansion, archive datetime/queryworthy checks, and archive scope-hint merge policy from `backend/app/services/research_service.py` into `backend/app/services/research/archive_context.py`.
- Kept `research_service.py` compatibility wrappers for archive-context tests and generation flow callers, reducing it from 15,333 to 15,177 lines.
- Updated `docs/module-ownership-map-2026-05-21.md` with the new collector ingest and research archive-context ownership rows plus current hotspot sizes.

Module boundary decision:

- Browser/plugin/URL ingest is its own collector API subdomain: it owns source URL normalization, item creation, ingest attempts, immediate processing, background processing, and browser fallback metadata for those routes.
- `collector.py` is now closer to a compatibility router for WeChat Favorites, OCR route entrypoints, retry/status, daemon, and WeChat agent operations.
- Archive context rendering and query expansion are retrieval/persistence support policy; the main research service should call them through wrappers instead of carrying prompt formatting and historical-scope merge rules inline.
- The remaining research service split should target generation execution and archive loading/persistence orchestration rather than pure helper moves.

Verified:

- `python3 -m py_compile backend/app/api/collector.py backend/app/api/collector_ingest.py backend/app/main.py`
- `.venv311/bin/python` route registry check for `/api/collector/browser/ingest`, `/api/collector/browser/batch-ingest`, `/api/collector/plugin/ingest`, `/api/collector/url/ingest`, and `/api/collector/ocr/ingest`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py`
- `python3 -m py_compile backend/app/services/research_service.py backend/app/services/research/archive_context.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py`
- `backend/.venv311/bin/pytest -q backend/tests/test_collector_process_immediate_ingest.py backend/tests/test_collector_ocr_quality.py backend/tests/test_collector_route_quality.py backend/tests/test_multiformat_collector_service.py backend/tests/test_research_archive_context.py backend/tests/test_research_report_storage_rewrite.py backend/tests/test_research_hybrid_retrieval.py backend/tests/test_research_report_evaluation_service.py`
- `npm run lint`
- `npm run build`
- `git diff --check`
