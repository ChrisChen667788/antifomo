# LangGraph Production Cutover v1.7.0

Version: `1.7.0+20260614`

## Decision

`langgraph` is the default research workflow engine. `deterministic` remains the immediate rollback engine, and `langgraph_shadow` remains a compatibility alias.

## Gate Evidence

- Dataset: `anti-fomo-research-golden-v1`
- Dataset version: `1.1.0`
- Status: `locked`
- Cases: `100`
- Suites: `10`
- Lock digest: `79eb5c4c9e5523a074cc2691f3f840e5488ce93623b946b103ee24e0ed103ec3`
- Offline deterministic/LangGraph parity: `100/100`
- Parity rate: `1.0`
- Network calls: none
- Model calls and token cost: none

Run the gate:

```bash
npm run research:evaluate:parity
```

The artifact is written to `.tmp/research-workflow-parity.json`.

## What The Gate Proves

- Both engines return the same report payload for the same owner-level setup and generation ports.
- Progress callbacks, snapshots, common workflow metrics, cost ledgers, and failure-free completion stay equivalent.
- All locked evaluation inputs can traverse the production graph contract.

## What The Gate Does Not Prove

- Live search availability or source freshness.
- Provider latency, token cost, or model-specific structured-output reliability.
- Retrieval relevance and final answer quality under real network/model conditions.

Those properties require the explicit cost-bearing command:

```bash
npm run research:evaluate -- --execute --workflow-engine langgraph --allow-live-provider
```

Use a bounded `--limit` first. Do not run the complete live suite without an approved provider-cost budget.

As of `1.7.1`, live execution also requires a complete independent review artifact, an explicit `--budget-usd`, and no more than five selected cases by default. See `docs/research-evaluation-governance-v1.7.1.md`.

## Rollback

Set:

```bash
RESEARCH_WORKFLOW_ENGINE=deterministic
```

No prompt, retrieval, ranking, storage, or delivery owner imports LangGraph, so rollback does not require domain-module changes.

## PostCSS Security Compatibility

Next.js `16.2.9` pins PostCSS `8.4.31`, which is affected by `GHSA-qx2v-qp2m-jg93`. The audit tool proposes an incompatible downgrade to Next.js 9, so `package.json` overrides PostCSS to `8.5.15`.

Release validation requires:

```bash
npm ls next postcss --all
npm audit --audit-level=moderate
npm run build
```

Remove the override only after a stable Next.js release uses `postcss>=8.5.10` and passes the same checks.
