# Backend and Frontend Hotspot Assessment - 2026-06-14

## Decision

No additional large-file split is required for `1.7.0`. The current hotspots are monitored, but line count alone is not an ownership boundary.

## Current Hotspots

| File | Lines | Current boundary judgment |
| --- | ---: | --- |
| `scripts/wechat_pc_full_auto_agent.py` | 5977 | Cohesive automation process with fragile UI/runtime coupling; split only when a daemon, OCR, or route-policy change creates a testable process boundary. |
| `backend/app/services/research_service.py` | 3739 | Compatibility and dependency-wiring facade; continue deleting proven dead wrappers or moving stable owner ports, not broad mechanical slicing. |
| `backend/app/services/wechat_pc_agent_daemon.py` | 2072 | Process supervision and persisted runtime state remain coupled; require a concrete state-store or supervisor change before extraction. |
| `backend/app/schemas/research.py` | 1867 | Large but cohesive public research DTO contract; split only with explicit import compatibility and schema ownership checks. |
| `backend/app/services/research_retrieval_index_service.py` | 1753 | Index lifecycle, chunk persistence, and query behavior are related; next split should follow a real storage/query adapter boundary. |
| `src/components/inbox/inbox-form.tsx` | 1638 | Pure preparation/model behavior is already extracted; further split should follow a stable visible section or controller change. |
| `backend/app/services/research_workspace_store.py` | 1638 | Persistence and version-comparison serialization are candidates, but need an API behavior change or dedicated owner tests first. |
| `backend/app/api/research.py` | 1635 | Route aggregation is large but thin; split by router only when deployment, authorization, or versioning policy differs. |

## Refactor Rule

Proceed only when all conditions hold:

1. The candidate responsibility has a stable name and at least two callers or an independently testable contract.
2. The extraction removes a dependency direction or compatibility seam instead of adding another wrapper.
3. Existing API, persistence, and monkeypatch contracts can be preserved or explicitly versioned.
4. Focused regression tests exist before the move.

The locked evaluation and workflow parity owners satisfy these conditions and were extracted in `1.7.0`. None of the remaining large-file candidates currently clears the same bar.
