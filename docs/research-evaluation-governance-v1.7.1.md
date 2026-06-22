# Research Evaluation Governance v1.7.1

Version: `1.7.1+20260614`

## Current Truth

The 100-case dataset is structurally curated and locked. In `1.7.2`, 78 reviewer comments were applied to region and research-subject precision without using reviewer name/date. This is recorded as scope-feedback resolution, not completed independent approval of the revised cases.

Independent review is complete only when a different reviewer:

1. Reviews all 100 cases.
2. Approves each behavior label, answer-term set, and expected source domain.
3. Writes a substantive note for every case.
4. Supplies reviewer name, role, date, and attestation.
5. Finalizes the artifact and passes digest validation.

## Review Workflow

Export:

```bash
npm run research:evaluate:review:export
```

Edit `.tmp/research-evaluation-independent-review.json`. The locked context
fields are read-only evidence, including `keyword`, `research_focus`,
`regions`, `entities`, behavior, answer terms, source domains, and curation
notes. Update only each case's `decision` and `notes`.

Finalize:

```bash
npm run research:evaluate:review:finalize -- \
  --review .tmp/research-evaluation-independent-review.json \
  --reviewer-name "<independent reviewer>" \
  --reviewer-role "<domain role>" \
  --attestation "I independently reviewed all cases against the locked criteria."
```

Validate:

```bash
npm run research:evaluate:review:validate -- \
  --review .tmp/research-evaluation-independent-review.json
```

Any changed locked context, including a changed region or research subject,
duplicate/missing case, non-approved decision, weak note, same reviewer as the
original locker, or digest mismatch blocks approval.

The content digest detects artifact changes after finalization. It is not a public-key cryptographic signature and does not prove the reviewer's real-world identity; reviewer identity governance remains an organizational responsibility.

## Live Evaluation Budget

Generate the plan:

```bash
npm run research:evaluate:plan-live
```

Current full-suite target ceiling:

- Cases: `100`
- Default batch size: `5`
- Batches: `20`
- Target cost ceiling: `$81.50`

The target ceiling comes from per-case `estimated_cost_usd` gate targets. It is a planning ceiling, not a provider invoice guarantee.

## Bounded Execution

Example one-case run after independent review:

```bash
npm run research:evaluate -- \
  --execute \
  --case-id gov-cloud-001 \
  --workflow-engine langgraph \
  --allow-live-provider \
  --review .tmp/research-evaluation-independent-review.json \
  --budget-usd 0.80
```

Safety rules:

- Live credentials require explicit `--allow-live-provider`.
- A validated independent review artifact is mandatory.
- An explicit approved budget is mandatory.
- The selected cases' target ceiling must fit the approved budget.
- No more than five live cases run per invocation unless the operator deliberately changes `--max-live-cases`.
- Missing provider pricing blocks all remaining cases.
- Observed spend above approval blocks all remaining cases.

Do not commit completed review artifacts if they contain reviewer personal information that is not intended for the public repository. Store public attestations deliberately; otherwise keep them in ignored `.tmp` storage.
