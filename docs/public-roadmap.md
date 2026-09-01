# Anti-FOMO Public Roadmap

This page is the stable, repository-local companion to the [public roadmap issue](https://github.com/ChrisChen667788/antifomo/issues/1). It explains the product direction in contributor-sized themes without treating a local implementation, demo fixture, or documentation update as a production release approval.

For the detailed, evidence-governed post-`2.9.5` plan, see the [Competitive Capability Observatory](./competitive-capability-observatory-v2.10.0.md), [reviewable decision contexts](./reviewable-decision-context-packets-v2.10.1.md), [artifact acceptance boundary](./artifact-acceptance-and-revision-diff-v2.10.2.md), and the current [2.10.3–2.11.7 Agent landscape and governed iteration train](./competitive-agent-landscape-and-iteration-program-2026-08-31.md).

## Operating boundary

The current release baseline remains `baseline_hybrid`; release promotion remains blocked until the required independent retrieval, human review, Office, visual, security, performance, recovery, and customer-acceptance evidence exists. A roadmap card answers *what the product should make reviewable next*; it never grants a release or an automation permission on its own.

## Near-term public themes

| Theme | User outcome | Publicly inspectable scope | Evidence needed before it is called complete |
| --- | --- | --- | --- |
| Collection reliability | Collect WeChat-heavy signals without duplicate, unexplained, or silently degraded results. | Accessibility-first navigation experiments, duplicate-screen diagnostics, route-level logs, structured URL/history handling, and explicit OCR fallback state. | Reproducible before/after samples, failure-mode logs, and a human review of the affected collector path. |
| Evidence-backed research | Turn collected material into a report whose claims, source revisions, retrieval state, and delivery status can be inspected. | Report persistence, source lineage, version comparison, clarification/recovery, watchlists, and retrieval assurance. | Fresh source records, fixed-cohort evaluation, independent review, and the existing release gates. |
| Execution and action cards | Turn a reviewed report into a bounded next action instead of an untraceable autonomous task. | Focus sessions, session-summary exports, action cards, briefs, follow-up drafts, watchlist digests, and explicit execution proposals. | A scoped permission/approval record, dry-run or replay evidence where automation is proposed, and human acceptance of the delivery artifact. |
| Multi-format intake | Keep one research workflow across web links, files, RSS/newsletters, and transcript-style sources. | Connector admission, parser/source diagnostics, deduplication, source taxonomy, and provenance-preserving imports. | Source-specific accuracy and failure evidence; licensed or private inputs remain outside the public demo unless explicitly authorized. |
| Product-strategy observability | Make competitor claims, non-goals, roadmap decisions, and delivery reviews inspectable rather than silently changing product direction. | Official-source snapshot ledger, reviewable decision contexts, and HOLD-only acceptance/revision records. | Fresh first-party sources plus an attributable human decision; a stored source or template is not external acceptance. |

## How the public surfaces connect

`collect -> clean -> research -> compare -> focus -> action`

The compact [product surface map](./product-surface-map.md) shows where each part of this loop lives, which inputs and outputs it owns, and how a reader can distinguish live, empty, local-demo, and degraded states.

## Contribution slices

1. Start with an observable user outcome and a small route, component, API, or script boundary.
2. State whether the change is documentation, UI, backend, collector, or an evidence-only workflow.
3. Add a reproducible verification step. For collector work, include the route/fallback path and an expected diagnostic; for research work, include provenance and test expectations.
4. Do not weaken release, evidence, permission, or fallback disclosure gates to make a demo look complete.

Current contributor-friendly items are kept in the [open-source backlog](./open-source-backlog.md). The public GitHub issues remain the source of truth for discussion and assignment; this page is the durable orientation layer for new readers.

## Status language

| Label | Meaning |
| --- | --- |
| `implemented` | Code and/or documentation exists in this checkout. It is not automatically production-approved. |
| `in progress` | The direction is accepted, but the bounded implementation or verification is unfinished. |
| `evidence-gated` | The code may exist, but outside evidence or human review is still required. |
| `defer` | The capability is intentionally not being enabled until its permission, safety, or verification design is accepted. |
