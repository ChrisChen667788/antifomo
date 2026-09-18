# Anti-FOMO Value Map

This map converts product capability into buyer-facing outcomes without turning local evidence into a production claim. Each scenario is intentionally written as `trigger → workflow → artifact → metric → evidence tier`.

## Scenario A: AI tender and market watch

- **Trigger:** A consultant needs to track official tenders, product changes and source freshness across a noisy WeChat/web stream.
- **Workflow:** source intake → canonicalization/dedupe → source health → retrieval → official-source comparison → watchlist digest → human review.
- **Artifact:** source matrix, change digest, stale/failed-source queue, reviewable follow-up actions.
- **Metric:** target is to reduce duplicate manual triage steps and make every stale source visible; exact time saved must be measured on a fixed before/after cohort.
- **Evidence tier:** current repository implementation + local monitor run + demo. Not customer ROI.

## Scenario B: Customer solution research

- **Trigger:** A solution architect must turn market research into a customer discussion before the next meeting.
- **Workflow:** research brief → claim/evidence ledger → compare workspace → architecture readiness → four-layer blueprint → ADR/risk list → customer questions and validation actions.
- **Artifact:** evidence-backed report, architecture blueprint, decision criteria, integration risks, meeting agenda and validation checklist.
- **Metric:** target is fewer handoff gaps between research and solution design; acceptance should measure field completeness, citation coverage and reviewer time on a fixed scenario set.
- **Evidence tier:** local implementation + generated artifacts. Customer acceptance is not present unless a named customer accepts a version.

## Scenario C: Biweekly competitor/model watch

- **Trigger:** Product and strategy teams need a repeatable review of changing model/Agent claims.
- **Workflow:** scheduled read-only source monitor → content digest → changed/stale source queue → evidence gate → issue/PR discussion → roadmap decision.
- **Artifact:** dated monitor report, source digest, issue comment, PR or roadmap decision record.
- **Metric:** target is predictable review cadence and zero silent source expiry; the source monitor’s success/failure counts are operational evidence, not product-market fit.
- **Evidence tier:** official source snapshot + local run + human decision record.

## What a buyer can verify in a demo

| Step | Visible proof | Boundary |
| --- | --- | --- |
| Intake | A WeChat/web source becomes a recoverable queue item | Local adapter and fixture; source permissions still apply |
| Evidence | A claim expands to source version, digest, freshness and HOLD reason | Citation coverage is not a guarantee that the claim is true |
| Architecture | A reviewed report becomes a blueprint and validation list | The blueprint is a draft until a qualified reviewer accepts it |
| Action | An action card records owner, next step and approval state | External writes/sends remain gated |
| Recovery | Failed source or task can be retried/replayed with a receipt | Reproducibility is bounded by source availability and model/provider drift |

## Buyer questions to answer before a pilot

1. Which sources are allowed, and what freshness window is required?
2. Which outputs need a human signature or customer acceptance?
3. Which connectors are read-only, and which may write after approval?
4. What is the maximum run time, concurrency, model spend and retry budget?
5. What must be exported if the pilot ends?
6. Which metric matters: triage time, citation completeness, review turnaround, artifact reuse, or meeting preparation time?

See [current product status](./current-product-status.md) for evidence labels and [the WorkBuddy comparison/integration plan](./marketing-overhaul-2026-09.md) for the next ten versions.
