# Backend Hotspot Assessment - 2026-06-05

## Scope

This assessment covers the next backend refactor candidates after the research wrapper migration work:

- `backend/app/services/knowledge_intelligence_service.py`
- `backend/app/services/work_task_service.py`
- residual `research_service.py` dependency seams referenced by these modules and tests

## Current Size And Risk

| File | Lines | Main responsibilities | Immediate risk |
| --- | ---: | --- | --- |
| `knowledge_intelligence_service.py` | 2709 | research intelligence extraction, metadata payloads, review queue resolution, report backfill, commercial dashboard aggregation | high: mixed persistence/backfill/dashboard/report rewrite ownership |
| `work_task_service.py` | 2058 | markdown/docx/pdf exports, work task completion helpers, research delivery artifacts | medium-high: export rendering and delivery builders are mixed with task state helpers |
| `research_service.py` | 7848 | compatibility wrapper plus residual orchestration helpers | high: still has residual private wrapper calls in tests and service imports |

## Progress Update

Completed in the current refactor slice:

1. `v0.9.1 - Ranking Owner Extraction`: added `backend/app/services/research/source_ranking.py`, moved hybrid hit/source reranking orchestration there, and migrated ranking tests away from `research_service._hybrid_rank_hits` and `research_service._rerank_sources_hybrid`.
2. `v0.9.2 - Knowledge Intelligence Wrapper Removal`: removed delayed `research_service` imports from `knowledge_intelligence_service.py`; report metadata/backfill now validates via `ResearchReportResponse` and uses knowledge-owned canonicalization for stored account cleanup.
3. `v0.9.3 - Work Task Export Import Cleanup`: changed `work_task_service.py` to import `build_research_report_markdown` directly from `app.services.research.report_markdown`.

Remaining seams after this slice:

- `test_research_hybrid_retrieval.py` still calls `research_service` compatibility wrappers for query-plan dependency factories, tender-detail dependency factory, scope inference, candidate-profile promotion, report readiness, commercial summary, technical appendix, review queue, and readiness guardrails.
- `knowledge_intelligence_service.py` no longer imports `research_service`, but full action-card regeneration during backfill is intentionally deferred until `research.action_cards` has an owner-level dependency factory.

## Findings

1. `knowledge_intelligence_service.py` should be the next backend hotspot.

   It still imports `app.services.research_service` inside runtime paths:

   - `build_research_report_metadata` enriches reports via `research_service._enrich_report_for_delivery`.
   - `_rewrite_stored_report_payload` validates/rewrites reports and builds action cards via `research_service`.

   These are direct wrapper-retirement blockers and should be migrated before more dashboard features are added.

2. `work_task_service.py` is also large, but the dependency seam is narrower.

   It imports `build_research_report_markdown` from `research_service`, even though the owner module already exists at `app.services.research.report_markdown`. This is a low-risk import migration, then the larger export split can happen separately.

3. `test_research_hybrid_retrieval.py` now has runtime/source-diagnostics/ranking owner coverage.

   The remaining calls should continue as small owner-module migrations rather than large test-only stubs.

## Recommended Iteration Plan

### v0.9.1 - Ranking Owner Extraction

Status: completed.

Goal: remove ranking seam from `test_research_hybrid_retrieval.py` without changing ranking behavior.

Implementation plan:

1. Create `backend/app/services/research/source_ranking.py`.
2. Move orchestration for hybrid search-hit ranking and source reranking into owner functions.
3. Introduce a `SourceRankingDependencies` dataclass only where private collaborators still live outside the new owner module.
4. Keep `research_service._hybrid_rank_hits` and `research_service._rerank_sources_hybrid` as thin compatibility wrappers.
5. Migrate ranking tests to import owner functions from `source_ranking.py`.
6. Verify with `backend/.venv311/bin/pytest -q backend/tests/test_research_hybrid_retrieval.py -k "hybrid_rank or source_rerank or cross_encoder"`.

### v0.9.2 - Knowledge Intelligence Wrapper Removal

Status: completed for direct `research_service` imports; full action-card backfill regeneration remains deferred.

Goal: remove `knowledge_intelligence_service.py` runtime imports of `research_service`.

Implementation plan:

1. Replace report model validation with direct schema imports from `app.schemas.research`.
2. Replace delivery enrichment with owner module `app.services.research.delivery_enrichment` and a local dependency factory.
3. Replace stored report rewrite calls with `app.services.research.stored_report_rewrite` owner functions and a local dependency factory.
4. Replace action card generation with `app.services.research.action_cards` owner module.
5. Add focused tests around metadata payload generation and backfill rewrite behavior.

### v0.9.3 - Work Task Export Import Cleanup

Status: completed.

Goal: remove the low-risk `work_task_service.py` import from `research_service`.

Implementation plan:

1. Change `from app.services.research_service import build_research_report_markdown` to `from app.services.research.report_markdown import build_research_report_markdown`.
2. Run existing work task/export tests.
3. If coverage is thin, add one regression test for `build_research_markdown`.

### v0.9.4 - Work Task Export Split

Goal: reduce `work_task_service.py` blast radius.

Implementation plan:

1. Extract simple PDF builder helpers to `app.services.work_task.pdf_export`.
2. Extract formal document section/context builders to `app.services.work_task.formal_documents`.
3. Extract research export wrappers to `app.services.work_task.research_exports`.
4. Leave task state transitions in `work_task_service.py`.

## Verification Commands

Use these as the baseline for the next backend slice:

```bash
backend/.venv311/bin/pytest -q backend/tests/test_research_hybrid_retrieval.py
backend/.venv311/bin/pytest -q backend/tests/test_research_report_evaluation_service.py
npm run security:scan
```
