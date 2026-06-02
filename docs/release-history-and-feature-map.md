# Release History and Feature Map

Current version: `1.1.0+20260602`

This file is the compact product map for release notes, GitHub updates, and future iteration planning. It groups historical major-version progress by capability layer and keeps the current feature inventory explicit enough for industry-facing delivery review.

For the upcoming modular architecture refactor and day/night design-system refresh, use `docs/current-version-and-refactor-roadmap-2026-05-20.md` as the working baseline.

## Major Version History

| Version line | Core iteration | What changed |
| --- | --- | --- |
| `0.3.x` | Research quality baseline | Stabilized compare/export delivery, archive snapshots, offline research metrics, evidence-backed report quality gates, section-level evidence packs, and methodology playbooks for government cloud, compute/LLM infrastructure, AI applications, and B2B solution research. |
| `0.4.x` | Retrieval substrate and delivery packs | Added persistent retrieval index, section routing, golden report evaluation, three-year tender/product intelligence, solution-delivery packs, feasibility-study and project-proposal exports, scenario refresh loops, and real GitHub product screenshots. |
| `0.5.x` | RAG quality engineering and knowledge cleanup | Added CRAG-style retrieval correction, generation grounding review, report self-evaluation, unified retrieval documents, schema-v2 chunks, stable chunk IDs, source cleaning, role-aware entity cleanup, watchlist operations health, and first reranker evaluation controls. |
| `0.6.0` | CrossEncoder reranker and advisory-grade delivery | Upgraded reranking to the SentenceTransformers CrossEncoder adapter with fallback diagnostics, added retrieval rebuild visualization, parent-block routing boost, watchlist run history, failed-run retry notes, notification summaries, Markdown digest export, client brief, bidding memo, execution materials, and semiconductor entity cleanup. |
| `0.6.1` | Quality-triggered public-source expansion | When self-evaluation stays weak, report and delivery generation can expand beyond configured sources into public procurement, official, disclosure, open-web, public-resource, and public WeChat search paths before re-evaluating quality. |
| `0.6.2` - `0.6.4` | China-tech delivery quality and diagnostics control plane | Added solution-pack and project-proposal quality scoring, deterministic self-review/self-repair, delivery regression metrics, query/routing/reranker A/B controls, follow-up delta offline evaluation, delivery export trend/version comparison, and rebuild/cache/recovery optimization panels. |
| `0.6.5` - `0.6.7` | Experiment orchestration and rollout audit | Promoted the diagnostics layer into persistent experiment plans with frozen cohorts, locked baselines, gate evaluation, gate history, rollout manifests, activation/revocation actions, and an active policy registry with same-lane supersede behavior. |
| `0.6.8` - `0.6.10` | Runtime strategy activation | Added runtime strategy snapshots, effective runtime config resolution, retrieval and section-pack strategy consumption, report-generation runtime strategy injection, source diagnostics, fallback-lane visibility, and report-generation config panels. |
| `0.6.11` | Release-grade GitHub documentation and screenshot coverage | Expanded automated screenshot capture to all primary product surfaces, added screenshot quality gates and a manifest, refreshed README links, and documented historical version progress plus the current complete capability map. |
| `0.7.0` | Focus collection reliability and source-health operations | Shifted Focus mode to a headless-source-first collector path, kept the WeChat PC agent as supplementary URL harvesting, and added run-level plus source-level health diagnostics so failed公众号 sources are visible by name instead of hidden inside aggregate coverage. |
| `0.8.0` | Solution architecture readiness for consultants | Added architecture readiness scoring, architecture blueprint sections, non-functional requirements, integration risks, assumptions, stakeholder questions, and validation actions to solution delivery packs and research report UI. |
| `0.8.1` | WeChat Favorites import and review queue | Added one-click WeChat Favorites preview/import for exported text, HTML, clipboard, shortcut files, raw/escaped/encoded公众号 links, persistent import batches, queue recovery, failed-item retry, and homepage swipe triage. |
| `0.9.0` | Solution architect workbench | Added customer scenarios, stakeholder question maps, decision criteria, validation actions, next-meeting agendas, markdown export, and research-report-card surfacing inside solution delivery packs. |
| `1.0.0` | Local-first WeChat-to-solution baseline | Connected WeChat-heavy intake, homepage triage, evidence-backed research, solution architecture readiness, architect workbench output, migration coverage, release metadata, and validation into one complete local-first baseline. |
| `1.1.0` | Modular architecture and semantic theme baseline | Refactored research generation, collector operations, delivery intelligence, feature clients, controller hooks, report panels, knowledge detail, and session summary surfaces into smaller modules while moving major UI surfaces to semantic day/night theme tokens. |

## Current Capability Inventory

### 1. Intake and Cleaning

- URL, text, RSS, newsletter, file, YouTube transcript, browser-extension, WeChat Favorites import, WeChat URL-first, headless source collector, collector daemon, and WeChat PC agent supplementary intake paths.
- WeChat Favorites import supports exported HTML/TXT, clipboard text, shortcut files, raw/escaped/encoded `mp.weixin.qq.com` links, preview before import, persistent batches, failed-item retry, and homepage queue recovery.
- Cleaning rules for OCR fragments, markdown/source dumps, weak vendor promotion, forum/award noise, and low-signal placeholder content.
- Entity-quality controls that prevent non-entity technical phrases and field labels from leaking into account, competitor, partner, and ranked-entity outputs.
- Collector coverage diagnostics now expose handled count, coverage rate, body success rate, per-source health state, poor/watch source counts, and operator recommendations.

### 2. Research and Retrieval

- Keyword research, topic tracking, follow-up generation, compare snapshots, archive history, and exportable markdown/PDF/brief paths.
- Persistent research retrieval index with resumable rebuild, incremental upsert, stable chunk IDs, sentence-window chunks, parent report/section links, and metadata filters.
- Section-level retrieval packs, parent-block routing boost, official-source bias, source diagnostics, and unsupported-claim detection.
- Optional CrossEncoder/SentenceTransformers reranking with local fallback and offline official-source Recall@5 evaluation.

### 3. Quality and Evaluation

- Research quality profile covering professional rigor, intelligence value, target-account support, section evidence quota, citation quality, entity recall, and grounding.
- CRAG-style source grading and corrective query planning.
- Follow-up delta evaluation for title handling, summary handling, impacted-section routing, and official-source support yield.
- Delivery-quality offline regressions for solution-delivery pass rate, project-proposal pass rate, and self-review gain rate.

### 4. Experiment Orchestration

- Query, routing, and reranker A/B control plane.
- Persisted experiment strategy plans, frozen cohorts, locked baselines, rollout gates, gate history, rollout manifests, active strategy registry, and revocation flow.
- Runtime strategy snapshot and effective runtime config for retrieval search, section packs, and report generation.
- Operator-facing warnings for fallback lanes, degraded strategies, baseline drift, and rollout readiness.

### 5. Advisory-Grade Delivery

- Market intelligence packs with three-year tender history, products, technical parameters, source queries, and evidence gaps.
- Scenario/customer/vertical-scene refresh loop before formal export.
- Feasibility study, project proposal, client-facing PPT outline, client brief, bidding prep memo, and execution-material chains.
- Solution architecture readiness for business alignment, capability boundaries, integration dependencies, security/compliance constraints, and delivery feasibility.
- Architecture blueprint export covering business/role, application capability, model/data/integration, and security/deployment/operations layers.
- Solution architect workbench output for customer scenarios, stakeholder concerns, decision questions, required materials, decision criteria, capability-to-architecture mappings, ADR-style decisions, integration dependency diagnostics, validation actions, and next-meeting agendas.
- China-tech delivery self-review and self-repair across demand, architecture, security/compliance, procurement/implementation, budget/performance, risks, acceptance, and evidence grounding.

### 6. Execution and Operations

- Focus sessions, session summary, markdown summary, reading list, todo drafts, exec brief, sales brief, outreach draft, and watchlist digest.
- Focus startup now ensures the headless source collector is running before starting the WeChat PC agent, so daily公众号 refreshes continue even when the desktop article-window path is unavailable.
- Watchlist run history, failed-run retry policy notes, notification summaries, daily briefs, and Markdown digest export.
- Collector operations panel for imports, source management, source health triage, OCR backfill, queue flush, daily export, automation state, and diagnostics.
- Settings and tuning surfaces for language, theme, typography, WorkBuddy, recommender preferences, collector operations, and preference insights.

### 7. Knowledge and Commercial Hub

- Knowledge library, account intelligence, opportunity summaries, review queues, benchmark cases, role views, and commercial follow-up cards.
- Knowledge-card detail, edit, and merge workflows.
- Account workspace links from research outputs into business-development and solution-delivery workflows.

## Industry-Standard Release Checks

Before pushing a new release, run and record:

```bash
npm run lint
npm run build
npm run test:backend
npm run demo:smoke
npm run repo:screenshots
git diff --check
```

Release material must satisfy:

- Product screenshots cover every primary function interface listed in `docs/feature-screenshot-coverage.md`.
- Screenshot manifest version matches `package.json`.
- README and Chinese README link to the full screenshot coverage and current capability map.
- Product whitepaper, launch kit, and growth copy reflect the current commercial positioning and release highlights.
- Changelog includes user-visible changes, quality gates, and screenshot/doc coverage changes.
- Demo data shown in screenshots must be specific enough to demonstrate value, with empty or low-quality screenshots filtered out before commit.
- Delivery output quality must be reviewed against China technology-industry expectations: evidence grounding, procurement readiness, implementation path, compliance/risk handling, acceptance criteria, and executive readability.
