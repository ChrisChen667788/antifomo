# Anti-FOMO Version Iteration Plan

Updated: 2026-05-13

Version rule: use `MAJOR.MINOR.PATCH+YYYYMMDD`, for example `0.3.1+20260423`.

Delivery note: the originally staged `0.3.2+20260424`, `0.3.3+20260425`, and `0.4.0+YYYYMMDD` work was implemented in order and shipped together as `0.4.0+20260423` because the actual implementation date is 2026-04-23.

## 0.3.1+20260423: Research Quality Profile

Goal: make every research report explicitly score professional rigor, intelligence value, actionability, and evidence strength.

Scope:

- Add an industry methodology playbook layer for government cloud, compute/LLM infrastructure, AI applications, and generic B2B solution research.
- Add report-level quality profile with dimension scores, strengths, gaps, and next actions.
- Add section-level evidence packs so weak chapters are visible before export or follow-up.
- Surface the quality profile in API types and the report card UI.

Acceptance:

- A generated or rewritten report contains `quality_profile`.
- Weak professional/intelligence dimensions produce concrete next actions.
- Section evidence gaps are linked to evidence quota and official-source counts.

## 0.3.2+20260424: Section Retrieval Packs

Goal: raise report factual density by feeding each important chapter with its own retrieval pack.

Status: delivered in `0.4.0+20260423`.

Scope:

- Build section retrieval targets from methodology axes.
- Route research retrieval index hits into chapter-specific evidence packs.
- Add context compression for official/procurement/source excerpts before generation. Current delivery exposes compressed snippets in section retrieval packs; generation-time injection remains a later optimization.
- Generate follow-up delta packs from supplemental evidence and previous report sections. Current delivery covers report-section routing; follow-up delta routing remains a later optimization.

Acceptance:

- Follow-up mode identifies changed sections instead of restating the full report. Pending deeper follow-up-delta integration.
- Each key chapter receives a ranked evidence pack before generation.
- Reports with weak packs are visible through pack status and next steps; automatic generation-time downgrade remains a later packaging optimization.

## 0.3.3+20260425: Golden Report Evaluation

Goal: make quality improvement measurable.

Status: delivered in `0.4.0+20260423`.

Scope:

- Add golden sample cases for government cloud, compute infrastructure, and AI application research.
- Track professional score, intelligence value score, target-account support, official-source ratio, and section evidence pass rate.
- Add CLI and API evaluation summaries for regression runs. Current delivery provides API/service evaluation; CLI wrapper remains optional.

Acceptance:

- `npm run check` keeps unit coverage.
- A separate evaluation command reports quality deltas for golden samples. Current service/API reports baseline metrics; historical delta storage remains a later enhancement.
- New retrieval/rerank changes must not lower core quality metrics without an explicit note.

## 0.4.0+YYYYMMDD: Persistent Research Retrieval Index

Goal: turn the current in-memory minimal index into a maintainable retrieval asset.

Status: delivered as `0.4.0+20260423`.

Scope:

- Persist chunks, parent-child links, metadata, and index schema version.
- Add incremental re-index and checkpointed rebuild.
- Add optional vector backend adapter while keeping local sparse+dense fallback. Current delivery keeps the storage boundary explicit for later Milvus/vector adapter work.
- Bring watchlist, commercial hub, archive recap, and knowledge account context into the same retrieval substrate. Current index covers research reports, report versions, compare snapshots, markdown archives, and knowledge entries.

Acceptance:

- Index rebuild can resume after interruption.
- Search can filter by document type, topic and source tier in service code; API currently exposes query/topic/limit and can be expanded for all filters.
- Generated reports and exports can cite index chunk IDs.

## 0.4.3+YYYYMMDD: Follow-up Delta Routing

Goal: make follow-up research runs visibly rework only the chapters affected by new evidence, new requirements, or narrowed target-account scope.

Status: delivered as `0.4.3+20260502`.

Scope:

- Add follow-up section impact diagnostics so every follow-up run lists impacted chapters, reasons, support score, and next action.
- Distinguish whether the final report title and executive summary stayed with the baseline draft or were corrected by the follow-up pass.
- Feed impacted-section hints into generation so follow-up mode rewrites the right chapters instead of flattening the full report.
- Surface impacted chapters and changed focus in report cards and follow-up workspace UI.

Acceptance:

- A follow-up run returns a structured list of impacted sections instead of only generic follow-up diagnostics.
- Users can see which sections changed because of new scope, new evidence, or new target-account constraints.
- Follow-up mode prioritizes affected sections in prompt context rather than treating the whole report equally.

## 0.5.0+YYYYMMDD: Unified Research Retrieval Substrate

Goal: turn the retrieval index into a shared substrate across reports, watchlists, compare snapshots, archive recap, and knowledge-account context.

Status: first wave delivered as `0.5.0+20260502` (cross-surface indexing + knowledge cleaning + entity quality). Follow-up closed in `0.5.2+20260507` with schema v2 chunks, sentence-window chunks, stable chunk IDs, parent-child report links, and broader API filters. Incremental rebuild visualization and parent-block routing boost shipped in `0.6.0+20260508`.

Scope:

- Bring watchlist refresh payloads, compare/export recap, commercial hub, and account context into the same retrieval index boundary.
- Add parent-child chunking, sentence-window chunks, richer metadata payloads, and stronger document-type filters.
- Keep stable chunk IDs across re-index so downstream compare/export can cite the same evidence anchors over time.
- Expose broader retrieval filters in service and API layers for topic, document type, source tier, and perspective.

Acceptance:

- One query can return cross-surface evidence blocks spanning research reports, knowledge entries, compare recap, and watchlist output.
- Compare/export and report delivery can cite chunk IDs without time drift after rebuild or resume.
- Incremental rebuild keeps document lineage stable enough for evidence appendix reuse.

## 0.5.1+YYYYMMDD: Retrieval Quality and Official-Source Biasing

Goal: materially raise professional rigor and intelligence value by improving what evidence is retrieved, compressed, and promoted.

Status: baseline delivered as `0.5.1+20260502` (CRAG retrieval correction profile + generation grounding review + report self-evaluation profile covering faithfulness / answer relevancy / context coverage / citation quality / entity recall). Follow-up advanced in `0.5.2+20260507` with a feature-flagged local cross-encoder-style reranker and offline official-source / unsupported-target metrics, then upgraded in `0.6.0+20260508` with a lazy SentenceTransformers CrossEncoder adapter and offline reranker official-source Recall@5.

Scope:

- Add reranker and context-compression hooks on top of the current hybrid retrieval baseline.
- Keep RRF as low-cost candidate generation for sparse + dense + scope signals; do not replace it globally at this stage.
- Add an optional `cross-encoder` top-k reranker behind feature flags for report-section retrieval, official-source promotion, and account-support verification. This is the default reranker path to validate first.
- Evaluate `cross-encoder/ms-marco-*` style rerankers against offline metrics including retrieval hit rate, target-account support rate, and section evidence pass rate before rollout.
- Strengthen routing boost for parent blocks, official sources, recency, target-account anchors, and procurement/budget signals.
- Continue suppressing bogus orgs, weak vendor push pieces, fake contact channels, and unsupported target-account claims.
- Expand region, industry, buyer, and scene suffix handling so vertical-scenario research stays within hard scope.

Acceptance:

- Official-source hit rate and target-account support rate trend upward on the offline panel.
- Bogus org rate and unsupported target-account rate trend downward.
- Section evidence packs show better support density without increasing scope drift.

## 0.5.2+YYYYMMDD: Continuous Research Workspace

Goal: make the research center operate like a durable workspace with refresh, compare, and operations loops instead of a one-shot generator.

Status: first wave delivered as `0.5.2+20260507` with Watchlist operations health summary, due / overdue / stale / failed-topic diagnostics, API client types, and research-center surfacing. Follow-up shipped in `0.6.0+20260508` with run history, failed-run retry, notification summaries, and Markdown digest export.

Scope:

- Add scheduled refresh, refresh diagnostics, and recurring monitoring queue for tracking topics and watchlists.
- Compare refresh runs across time and show what changed in targets, budgets, competitors, and evidence quality.
- Add saved views, latest linked report, refresh note, and failure hints to close the operator loop.
- Keep archive diff recap, compare recap, and export artifacts aligned with refresh history.

Acceptance:

- Tracking topics and watchlists can refresh on schedule with visible failure reasons.
- Users can compare two refresh runs and quickly see net-new evidence and changed commercial posture.
- Refresh artifacts, compare recap, and export views stay linked to the same topic history.

## 0.6.0+YYYYMMDD: Advisory-Grade Delivery Chain

Goal: upgrade output from useful research notes to advisory-grade delivery materials for solution design, selling, and bidding.

Status: first wave delivered as `0.6.0+20260508` with client brief, bidding prep memo, and execution materials generated from the solution delivery pack while preserving source policy and review checklist metadata. The delivery chain was strengthened in `0.6.2+20260513` with China-tech delivery quality review, proposal/feasibility self-audit, and structural self-repair before export.

Scope:

- Standardize client briefing, bidding prep memo, ecosystem outreach memo, and executive brief around the same section-level evidence packs.
- Keep feasibility study, project proposal, and client PPT outline tied to evidence anchors, insufficiency notes, and follow-up actions.
- Improve formal document tone, section ordering, and delivery templates for external-facing use.
- Ensure export chains preserve evidence appendix, official-source ratio, and unsupported-claim warnings.

Acceptance:

- Exported delivery artifacts can be traced back to section evidence and next-step verification paths.
- Formal documents no longer hide evidence gaps behind polished wording.
- Compare/export, follow-up delivery, and advisory templates share the same frozen evidence basis.

## 0.6.1+20260510: Quality-Triggered Public Evidence Expansion

Goal: when research quality is only average, expand public evidence beyond configured source settings before generating higher-stakes advisory materials.

Status: delivered as `0.6.1+20260510`.

Scope:

- Trigger public-source expansion when report evaluation remains watch/fail or source support is too weak for delivery materials.
- Search procurement, public-resource, official, disclosure, open-web, and public WeChat channels outside the active source-setting boundary.
- Merge new evidence, rebuild diagnostics and advisory materials, then re-evaluate quality before exposing the result.

Acceptance:

- Watch/fail reports can add public evidence without manual source reconfiguration.
- Delivery materials are regenerated from the merged evidence basis rather than from the weaker first-pass pack.
- The report card exposes expansion rounds, added sources, query plan, and score movement.

## 0.6.2+YYYYMMDD: Evaluation, A/B, and Performance Control Plane

Goal: make quality improvement and retrieval/runtime optimization measurable, repeatable, and safe to iterate.

Status: first control-plane tranche delivered as `0.6.2+20260513` with solution-delivery and proposal-grade quality review, auto-repair, export audit notes, and UI surfacing. `0.6.3+20260513` then wired delivery pass rates and self-review gain rates into offline regressions, weak-sample surfacing, and compare-snapshot compatibility. Broader A/B and runtime controls remain next.

Scope:

- Extend offline evaluation with golden reports, low-quality queue, follow-up delta behavior, and delivery export diagnostics.
- Track retrieval hit rate, target-account support rate, section evidence pass rate, official-source recall@k, bogus org rate, unsupported target-account rate, and delta evidence yield.
- Add A/B hooks for chunking, reranking, query planning, routing policy, and official-source bias.
- Evaluate `ColBERTv2` / `PLAID` only after the persistent retrieval substrate is stable enough to support a heavier multi-vector index. Treat it as a retrieval-engine upgrade candidate, not a drop-in reranker replacement for the current local RRF path.
- Improve performance with embedding/cache reuse, incremental re-index, checkpointed rebuild, and batched recovery tooling.

Acceptance:

- Retrieval and generation changes can be judged on fixed quality metrics instead of ad hoc inspection.
- Backfill, rebuild, and rewrite jobs are restartable and measurably faster.
- The project can iterate on report quality, evidence quality, and export quality with explicit regression guards.
