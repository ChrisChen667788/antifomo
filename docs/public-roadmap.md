# Anti-FOMO Public Roadmap

This page is the stable, repository-local companion to the [public roadmap issue](https://github.com/ChrisChen667788/antifomo/issues/1). It explains product direction in contributor-sized themes without treating a local implementation, demo fixture, or documentation update as production release approval.

The **authoritative ten-version engineering contract** is [WorkBuddy integration plan 2026-09-18](./workbuddy-integration-plan-2026-09-18.md), reviewed on 2026-09-22. It owns the `2.12.0`–`2.21.0` API/state/migration/PR/performance/rollback/DoD details. The [deep comparison](./workbuddy-deep-dive-2026-09-18.md) owns vendor sources, product boundaries and the three comparison protocols; its `R01–R10` identifiers are research work packages, not another release series. The [marketing overhaul](./marketing-overhaul-2026-09.md) owns narrative, diagrams and campaign assets. The canonical current-state and evidence labels are in [Current product status](./current-product-status.md).

For the already completed development line, see the [Competitive Capability Observatory](./competitive-capability-observatory-v2.10.0.md), [reviewable decision contexts](./reviewable-decision-context-packets-v2.10.1.md), [artifact acceptance boundary](./artifact-acceptance-and-revision-diff-v2.10.2.md), the [2.10.6–2.10.8 evidence closure](./2.10.6-2.10.8-evidence-closure.md), the [2.10.9–2.11.8 control-plane closure](./2.10.9-2.11.8-control-plane-closure.md), and the [2.10.3–2.11.8 Agent landscape and governed iteration train](./competitive-agent-landscape-and-iteration-program-2026-08-31.md).

## Operating boundary

The current release baseline remains `baseline_hybrid`; release promotion remains blocked until the required independent retrieval, human review, Office, visual, security, performance, recovery, and customer-acceptance evidence exists. A roadmap card answers *what the product should make reviewable next*; it never grants a release or an automation permission on its own.

The next ten versions remain `planned` until their feature flags, migrations, tests, and evidence gates pass. `2.14.0` begins with a bounded single-process SQLite queue and existing `ResearchJob` lease/recovery; it is not a claim of a distributed durable queue. External writes are idempotent with `unknown`/manual reconcile handling; exactly-once external effects are not promised. A real pilot is an external acceptance dependency, not an automatic outcome of `2.21.0`.

The current WorkBuddy bridge is a local export/CLI compatibility path. Its webhook verifies signatures only when a secret is configured; without one it reports `signature_bypassed_no_secret`, then can execute allowlisted exports and send a callback. It is not a general approval system. Version 2.12.0 must govern both that webhook and the existing `/api/tasks` entry point before wider execution is enabled. New envelopes use `/api/task-envelopes`, preserving the existing task API namespace. Feature-flag rollback must keep authorization and tenant isolation in force.

All future latency, error-rate, recovery and benchmark thresholds are acceptance targets, not achieved guarantees or production SLAs. Manual vendor-page rechecks do not renew the machine source-monitor registry or clear stale-source issues.

## Near-term public themes

| Theme | User outcome | Publicly inspectable scope | Evidence needed before it is called complete |
| --- | --- | --- | --- |
| Collection reliability | Collect WeChat-heavy signals without duplicate, unexplained, or silently degraded results. | Accessibility-first navigation experiments, duplicate-screen diagnostics, route-level logs, structured URL/history handling, and explicit OCR fallback state. | Reproducible before/after samples, failure-mode logs, and a human review of the affected collector path. |
| Evidence-backed research | Turn collected material into a report whose claims, source revisions, retrieval state, and delivery status can be inspected. | Report persistence, source lineage, version comparison, clarification/recovery, watchlists, and retrieval assurance. | Fresh source records, fixed-cohort evaluation, independent review, and the existing release gates. |
| Execution and action cards | Turn a reviewed report into a bounded next action instead of an untraceable autonomous task. | Focus sessions, session-summary exports, action cards, briefs, follow-up drafts, watchlist digests, and explicit execution proposals. | A scoped permission/approval record, dry-run or replay evidence where automation is proposed, and human acceptance of the delivery artifact. |
| Multi-format intake | Keep one research workflow across web links, files, RSS/newsletters, and transcript-style sources. | Connector admission, parser/source diagnostics, deduplication, source taxonomy, and provenance-preserving imports. | Source-specific accuracy and failure evidence; licensed or private inputs remain outside the public demo unless explicitly authorized. |
| Governed agent execution | Make WorkBuddy-like planning, skills, connectors, schedules, and mobile continuity safe for an evidence-aware research product. | Task envelopes, Ask/Plan/Agent states, model profiles, bounded lanes, registry/revocation, review inbox, usage ledger, and solution-architecture workbench. | The per-version contract in the [integration plan](./workbuddy-integration-plan-2026-09-18.md): fixed fixtures, failure injection, restart/replay, permission negatives, and human/externally attributable acceptance where required. |
| Product-strategy observability | Make competitor claims, non-goals, roadmap decisions, and delivery reviews inspectable rather than silently changing product direction. | Official-source snapshot ledger, reviewable decision contexts, and HOLD-only acceptance/revision records. | Fresh first-party sources plus an attributable human decision; a stored source or template is not external acceptance. |

## How the public surfaces connect

`collect -> clean -> research -> compare -> focus -> action`

The compact [product surface map](./product-surface-map.md) shows where each part of this loop lives, which inputs and outputs it owns, and how a reader can distinguish live, empty, local-demo, and degraded states. The planned governed execution path is described in [the integration plan](./workbuddy-integration-plan-2026-09-18.md), not inferred from this diagram.

## Contribution slices

1. Start with an observable user outcome and a small route, component, API, or script boundary.
2. State whether the change is documentation, UI, backend, collector, or an evidence-only workflow.
3. Add a reproducible verification step. For collector work, include the route/fallback path and an expected diagnostic; for research work, include provenance and test expectations.
4. For planned `2.12.0`–`2.21.0` work, link the relevant version section in the [integration plan](./workbuddy-integration-plan-2026-09-18.md), including feature flag, migration, rollback, and evidence level.
5. Do not weaken release, evidence, permission, or fallback disclosure gates to make a demo look complete.

Current contributor-friendly items are kept in the [open-source backlog](./open-source-backlog.md). The public GitHub issues remain the source of truth for discussion and assignment; this page is the durable orientation layer for new readers.

## Status language

| Label | Meaning |
| --- | --- |
| `planned` | Direction is documented but code and evidence are not yet delivered. |
| `implemented` | Code and/or documentation exists in this checkout. It is not automatically production-approved. |
| `in progress` | The direction is accepted, but the bounded implementation or verification is unfinished. |
| `evidence-gated` | Code may exist, but outside evidence or human review is still required. |
| `customer-acceptance` | A named external reviewer/customer accepted a scoped artifact with version and receipt. This cannot be inferred from a local demo. |
| `defer` | The capability is intentionally not being enabled until its permission, safety, or verification design is accepted. |
