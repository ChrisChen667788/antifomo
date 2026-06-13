# LangGraph Shadow Runtime v1.4.0

Anti-FOMO now includes a LangGraph orchestration adapter behind the existing framework-neutral `ResearchWorkflowEngine` protocol.

## Runtime Policy

- Production remains `deterministic` by default.
- `langgraph_shadow` is opt-in through `RESEARCH_WORKFLOW_ENGINE` or the evaluation CLI.
- The graph adapter reuses the same setup and generation dependency ports as the deterministic engine.
- Prompt, retrieval, ranking, storage, and delivery owners do not import LangGraph.

## Graph

```text
START -> prepare -> generate -> finalize -> END
```

The graph state contains only the research request, prepared setup, and final report. Callbacks and run metrics stay in the execution boundary instead of becoming persisted graph state.

## Evaluation

Validate the dataset:

```bash
npm run research:evaluate
```

Run a bounded graph baseline:

```bash
npm run research:evaluate -- --execute --limit 5 --workflow-engine langgraph_shadow
```

Remote provider credentials still require `--allow-live-provider`. The graph adapter must remain shadow-only until deterministic parity, failure recovery, latency, cost, and output-quality gates are measured on a locked dataset.
