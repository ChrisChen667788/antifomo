# LangGraph Shadow Runtime v1.4.0

Anti-FOMO now includes a LangGraph orchestration adapter behind the existing framework-neutral `ResearchWorkflowEngine` protocol.

Status: historical shadow-stage record. LangGraph became the production default in `1.7.0` after the locked 100-case offline parity gate passed 100/100.

## Runtime Policy

- The `1.4.0` production default remained `deterministic`.
- The `1.4.0` graph engine was selected through `langgraph_shadow`; this name remains a compatibility alias for `langgraph`.
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

Remote provider credentials still require `--allow-live-provider`. See `docs/langgraph-production-v1.7.0.md` for the production cutover evidence and the boundary between offline parity and live quality evaluation.
