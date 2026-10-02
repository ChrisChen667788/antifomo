# Task Envelope Control Plane

Status: `2.12.0 PR-A schema/state subset — local_implementation`

Updated: 2026-10-02

PR-A establishes the data and state boundary for governed tasks. It does not execute a task, create a legacy `WorkTask`, or send a callback. `ANTI_FOMO_TASK_ENVELOPE=0` remains the default reserved execution gate, but it does not disable the current proposal/control API; `execution_available` is always `false` in this slice.

## Persisted contract

| Table | Purpose | Mutation boundary |
| --- | --- | --- |
| `task_envelopes` | Current owner, mode, capability, frozen digests, budget/scope, state, approval pointer and revocation epoch | State-machine updates only |
| `task_approvals` | Approval bound to plan/content/effects, exact scope and budget, approver, expiry and revocation epoch | Append-only |
| `task_receipts` | Digest-chained proposal, approval, cancellation and reconciliation events | Append-only |
| `model_profiles` | Versioned provider/model/revision, token/runtime/cost ceiling and fallback order | Append-only |

Alembic revision `20261001_0040` is expand-only. Its downgrade is intentionally a no-op and retains all four tables and their evidence. A later executor must honor the reserved feature flag without deleting proposals or receipts.

## API boundary

- `POST /api/task-envelopes` creates `proposed`, `planned`, or `hold` from server-owned rules. A caller cannot set state.
- `GET /api/task-envelopes/{task_id}` is scoped to the configured `single_user_id` and verifies approval and receipt digests before returning data; this is not multi-user authentication or tenant isolation.
- `POST /api/task-envelopes/{task_id}/approve` accepts only a `planned` envelope and requires an exact context/plan/content/effects/scope/budget/revocation match plus a future expiry.
- `POST /api/task-envelopes/{task_id}/cancel` revokes the current approval epoch and records an immutable cancellation receipt.
- `POST /api/task-envelopes/{task_id}/reconcile` accepts only `unknown` or `reconcile_required`; PR-A does not itself create those execution states.

An idempotency key is globally unique so a replay by another user is rejected instead of silently attaching to that user's task. An identical owner replay returns the original envelope. Reusing the key with changed content returns a structured conflict.

## Authorization boundary

- `/approve` verifies the frozen envelope digests, exact scope/budget values, expiry and revocation epoch. It does not authenticate a human reviewer or evaluate a capability allowlist.
- `approver`, receipt `actor`, and scope names are caller-supplied strings. They are auditable assertions, not trusted identity or permission evidence.
- `ask|plan|agent` are recorded modes in this subset; Ask read-only and Agent execution policies are not implemented yet.
- `ModelProfile` has schema, service and tests, but no public registration API, default routing policy, or allowlisted fallback policy in PR-A.

## State boundary

Creation may produce `proposed`, `planned`, or `hold`. Approval permits only `planned → approved`; cancellation permits `proposed|planned|approved|hold|reconcile_required → cancelled`. Execution-owned states (`running`, `succeeded`, `failed`, `unknown`) cannot be selected by create or approval calls. A cancelled or expired approval cannot be revived by retrying its reference.

## Compatibility boundary

The legacy WorkBuddy webhook, `POST /api/tasks`, and Focus Assistant action service still call `create_and_execute_task` directly. Changing those responses also requires the current Web export flows and WorkBuddy panel to understand proposal and receipt states. That work is PR-B/PR-C and remains open; until it lands, PR-A must not be described as a universal approval gate or a complete 2.12.0 release.

## Reproducible checks

```bash
cd backend
.venv311/bin/pytest -q \
  tests/test_task_envelope_service.py \
  tests/test_task_envelope_api.py \
  tests/test_task_envelope_migration.py \
  tests/test_office_evidence_migration.py
```

The focused suite covers 100 concurrent same-key submissions, cross-user replay, changed digests, expired and revoked approvals, budget/scope mismatch, invalid transitions, append-only database guards, and a real `0035 → 0040` schema/stamp-drift upgrade. Passing it is local engineering evidence only.
