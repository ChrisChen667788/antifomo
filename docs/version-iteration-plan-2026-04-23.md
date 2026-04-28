# Anti-FOMO Version Iteration Plan

Updated: 2026-04-23

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
