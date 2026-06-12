# Research Workflow Baseline v1.1.1

## Purpose

This baseline creates a measurable orchestration boundary before adding LangChain or LangGraph. It preserves the current deterministic research behavior and API response while making runtime, cost, and evaluation contracts explicit.

## Runtime Contracts

- `ResearchWorkflowEngine` is the framework-neutral execution protocol.
- `DeterministicResearchWorkflowEngine` remains the only production engine in v1.1.1.
- `ResearchWorkflowExecution` returns the existing report plus per-run metrics.
- `generate_research_report()` remains backward compatible and unwraps the report.
- `execute_research_report_workflow()` exposes the report and metrics for benchmarks and future shadow runs.

## Metrics and Cost Ledger

`ResearchRunMetrics` records:

- total workflow duration and status;
- setup and generation node latency;
- progress-stage latency;
- source and section counts;
- counters and gauges that later workflow nodes can extend.

`CostLedger` records model-call operation, provider, model, status, outer-call attempts, latency, cache state, token counts, and estimated cost. Current token counts are explicitly marked as estimates because the legacy LLM interface only returns message content. Dollar cost remains `null` until a provider/model pricing configuration is introduced; the baseline does not invent prices or report unknown cost as zero.

Metrics logs contain operational metadata only. Prompt contents, source text, API keys, and user secrets are not written to the metrics snapshot.

## Evaluation Dataset

`backend/evaluation/research_golden_v1.json` defines exactly 100 draft cases across ten suites:

1. Government and public sector
2. Compute and LLM infrastructure
3. AI content and media
4. Healthcare AI
5. Education AI
6. Industrial and manufacturing AI
7. Energy and utilities
8. Financial services AI
9. Transportation and smart city
10. Weak evidence and guardrails

Each expanded case includes expected methodology, expected answer/guard/refuse behavior, scope anchors, required terms, preferred source tiers, required report sections, and targets for Recall@5, MRR, NDCG@5, citation support, answer correctness, refusal accuracy, latency, and cost.

The dataset status is `draft`. Before it is used as a release gate, every case needs human-reviewed source references, expected evidence, and answer-level assertions. Existing synthetic report fixtures remain unit-level quality checks and are not represented as a 100-case curated benchmark.

## LangChain and LangGraph Boundary

LangChain is intentionally not installed in this release. The next adapter must implement the existing model boundary and provide provider-native usage, structured output, retries, and configurable pricing without leaking framework objects into owner modules.

LangGraph is intentionally not installed in this release. A future graph engine should implement `ResearchWorkflowEngine` and initially run in shadow mode. Entity rules, source ranking, canonicalization, delivery rendering, and storage owners remain deterministic modules rather than graph-specific nodes with duplicated logic.

## Validation

Required checks:

```bash
npm run security:scan
npm run test:backend
git diff --check
```

Git-history secret rewriting remains a separate operation because it changes commit IDs and requires coordinated force-push handling.
