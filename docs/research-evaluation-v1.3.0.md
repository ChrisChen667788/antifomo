# Research Evaluation Runner v1.3.0

The research evaluation baseline is executable without coupling domain code to LangChain or LangGraph. As of `1.7.2`, the 100-case dataset is locked at dataset version `1.2.0` after 78 region/research-subject scope corrections.

## Commands

Validate the versioned 100-case manifest without running research:

```bash
npm run research:evaluate
```

Run a bounded mock-provider baseline and write a JSON artifact:

```bash
npm run research:evaluate -- --execute --limit 5 --output .tmp/research-evaluation.json
```

If remote provider credentials are active, execution is blocked unless `--allow-live-provider` is supplied explicitly.

Run the complete no-network orchestration parity gate:

```bash
npm run research:evaluate:parity
```

Export the independent human-review packet:

```bash
npm run research:evaluate:review:export
```

The generated packet carries the current locked `regions` and `entities` for
every case in addition to behavior, answer terms, and source domains. This is
required so the `1.7.2` scope corrections can be independently reviewed rather
than merely inherited from the dataset digest.

After a reviewer fills every case decision and note, finalize and validate it:

```bash
npm run research:evaluate:review:finalize -- \
  --review .tmp/research-evaluation-independent-review.json \
  --reviewer-name "<independent reviewer>" \
  --reviewer-role "<domain role>" \
  --attestation "<independent review attestation>"

npm run research:evaluate:review:validate -- \
  --review .tmp/research-evaluation-independent-review.json
```

Plan live-provider batches and their target cost ceiling:

```bash
npm run research:evaluate:plan-live
```

The complete current dataset has a target cost ceiling of `$81.50` and is divided into 20 default batches of five. Live execution requires both a validated independent review artifact and an explicit `--budget-usd`; one invocation is limited to five cases by default.

## Metric Integrity

- `citation_support_rate`, required-term coverage, behavior accuracy, latency, and configured cost are computed from each workflow result.
- `recall_at_5`, `MRR`, and `NDCG@5` are only computed when reviewed expected source domains or URLs exist.
- Missing source gold labels remain `unavailable`; they are never replaced with keyword-match proxies.
- A release gate requires a `locked` dataset, all 100 cases, all required metrics, and passing targets.

The current dataset is `locked`, includes explicit reference terms and first-party source-domain expectations for all 100 cases, and is protected by a content digest. The `1.2.0` scope revision applied reviewer comments while intentionally ignoring reviewer name/date per operator instruction. That makes the comments actionable curation input, not an independently signed approval of the revised cases. The offline parity gate proves orchestration-contract equivalence only; it does not replace a live retrieval and model-quality run.
