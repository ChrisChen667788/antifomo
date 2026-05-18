# Anti-FOMO Product Whitepaper

Version: `0.8.0+20260518`

Anti-FOMO is an open-source AI research workspace for turning noisy web and WeChat-heavy information flows into evidence-backed reports, solution architecture blueprints, focus sessions, and action-ready follow-up.

The product is designed for solution architects, industry consultants, BD and pre-sales teams, strategy operators, and builders who need a traceable path from raw signals to practical decisions.

## Executive Summary

Most information tools solve one step: saving links, summarizing content, searching notes, or exporting documents. Anti-FOMO is built around the whole operating loop:

`collect -> clean -> research -> compare -> focus -> action`

The 0.8.0 release strengthens the solution-architecture layer. Generated solution packs now include architecture readiness scoring, blueprint layers, integration risks, non-functional requirements, stakeholder questions, and validation actions so solution architects and industry consultants can move from research to client-ready architecture discussion.

## Problem

High-signal work often starts in fragmented channels: WeChat official accounts, article links, web pages, newsletters, files, and internal follow-up notes. The common failure modes are:

- promising articles are collected inconsistently
- source quality is invisible until the report is weak
- generic summaries lose evidence lineage
- research, comparison, execution, and delivery live in different tools
- teams cannot tell whether a bad output came from poor collection, weak retrieval, or missing scenario context
- solution architects still need to manually translate research into architecture boundaries, interface risks, security constraints, and implementation validation questions

Anti-FOMO treats collection reliability, evidence quality, and execution output as one product system.

## Product Architecture

### 1. Collection Layer

- URL, text, RSS, newsletter, file, YouTube transcript, browser extension, miniapp, and WeChat-heavy intake paths.
- Headless source collector for recurring公众号 source pages.
- WeChat PC agent as supplementary URL discovery when desktop automation is available.
- Collector daemon status with run-level coverage and per-source diagnostics.

### 2. Cleaning Layer

- Removes screenshot OCR fragments, markdown/source dumps, weak vendor promotion, forum/award noise, and low-signal placeholders.
- Normalizes source titles and content before downstream research.
- Protects account and entity surfaces from technical phrases that look like organization names.

### 3. Research Layer

- Keyword research, topic workspaces, follow-up research, compare snapshots, archive viewers, and formal exports.
- Persistent retrieval index with resumable rebuild, section routing, parent-block linking, and official-source bias.
- Quality profiles for professional rigor, evidence strength, target-account support, citation quality, and grounding.

### 4. Control Plane

- Experiment plans for query, routing, and reranker strategies.
- Frozen cohorts, locked baselines, rollout gates, active policy registry, runtime strategy snapshots, and effective runtime config.
- Delivery-quality regressions for solution packs and proposal-grade outputs.

### 5. Execution and Delivery Layer

- Focus sessions, session summaries, reading lists, todo drafts, exec briefs, sales briefs, outreach drafts, and watchlist digests.
- Feasibility studies, project proposals, client PPT outlines, client briefs, bidding prep memos, and execution-material chains.
- Solution architecture readiness with business alignment, architecture completeness, integration readiness, security/compliance readiness, and delivery feasibility scoring.
- Architecture blueprint sections for business/role, application capability, model/data/integration, and security/deployment/operations layers.
- Commercial Hub surfaces that turn research output into account intelligence, opportunities, review queues, and next actions.

## 0.8.0 Solution Architecture Release

The 0.8.0 release focuses on visible quality gains for solution architects and industry consultants.

New release capabilities:

- Architecture readiness score inside every generated solution delivery pack.
- Five review dimensions: business alignment, architecture completeness, integration readiness, security/compliance readiness, and delivery feasibility.
- Architecture blueprint sections with components, evidence, and open questions.
- Non-functional requirements, integration risks, assumptions, stakeholder questions, and validation actions.
- Research report card rendering for architecture readiness, blueprint layers, risks, and next actions.
- Solution delivery markdown export with a dedicated architecture-readiness chapter.

Commercial value:

- Helps solution architects turn noisy market and procurement signals into a structured client architecture narrative.
- Gives industry consultants a reusable bridge from research evidence to advisory deliverables.
- Makes pre-sales work more reviewable before client meetings, bid preparation, or project proposal export.
- Separates evidence-backed architecture statements from assumptions that still require customer confirmation.

## 0.7.0 Reliability Release

The 0.7.0 release addresses a practical operator problem: aggregate collector coverage is not enough. Users need to know which source failed.

New release capabilities:

- Focus start/resume ensures the headless source collector daemon is running.
- WeChat PC agent remains available as a supplementary URL harvester.
- Collector status reports handled count, coverage rate, body success rate, coverage state, and recovery guidance.
- Collector reports persist per-source summaries for scanned, discovered, queued, collected, deduplicated, skipped, failed, and unscanned sources.
- Backend, web Focus, Collector Ops, miniapp fallback, and release docs expose source health fields.
- Source health states use good, watch, and poor labels, while recommendations distinguish failed discovery, stale coverage, skipped links, and unscanned source conditions.

Commercial value:

- Faster diagnosis when a daily source stops producing usable articles.
- Lower dependence on fragile desktop automation.
- Better confidence that weak reports are caused by evidence gaps rather than silent collector failures.
- Clearer operations handoff for teams maintaining公众号 source lists.

## Target Users

- Solution architects preparing architecture narratives, capability maps, integration plans, and client discussion materials.
- Industry consultants preparing evidence-backed opportunity studies, advisory deliverables, and project proposal inputs.
- BD, pre-sales, and solution teams tracking accounts, tenders, competitors, and market movements.
- Founders and product leads who need repeatable research workflows across fast-moving AI and technology markets.
- Operators who live in WeChat article flows but need evidence lineage, not just saved links.
- Developers who want a local-first, inspectable research system instead of a black box SaaS.

## Deployment and Trust Model

Anti-FOMO is local-first by default:

- Next.js frontend and FastAPI backend run locally.
- SQLite supports the demo and development path.
- Runtime secrets, private user data, local databases, collector logs, and production miniapp credentials are excluded from the public repo.
- The codebase keeps testable service boundaries for collector, retrieval, research, delivery, and frontend surfaces.

The public repository is intended to be inspectable, modifiable, and practical for design partners before any hosted SaaS path.

## Release-Grade Product Evidence

The repository maintains commercial-standard release assets:

- README and Chinese README with current product screenshots.
- Full screenshot coverage in `docs/feature-screenshot-coverage.md`.
- Historical capability map in `docs/release-history-and-feature-map.md`.
- Launch kit in `docs/open-source-launch-kit.md`.
- Growth copy kit in `docs/open-source-growth-copy.md`.
- Changelog and package metadata aligned to the released version.

## Positioning

Anti-FOMO is not a read-later app, not a generic summarizer, and not only a RAG demo. It is an execution-oriented research workspace for teams that need:

- reliable high-signal intake
- evidence-aware research generation
- measurable quality controls
- side-by-side version comparison
- focus sessions and action outputs
- delivery-grade artifacts for client, opportunity, and strategy work
- solution architecture readiness and blueprint exports for pre-sales and consulting workflows

The product direction is to keep the core local-first and open-source while expanding reliability, evaluation, and commercial workflow depth.
