# 2.10.2 Artifact Acceptance and Revision Diff

Status: `2.10.2-development` is locally implemented as a HOLD-only review control plane. It is not an Office-file inspection, visual-render validation, artifact acceptance, production authorization, or release approval.

## Purpose and boundary

The four allowed `2.10.1` product-strategy context packets can now be bound to reviewable delivery-artifact acceptance drafts. The slice captures the evidence that is still absent and makes the resulting block explicit:

`persisted decision-context packet -> review draft -> immutable revision snapshot -> field-level diff -> human evidence review`

It intentionally does **not** turn a generated template, source digest, static test, or UI panel into proof that an Office document opens correctly or that a visual deliverable is readable.

## Current evidence gate

Every draft starts with all of the following required checks in `hold`:

| Required check | Current evidence state | Effect |
| --- | --- | --- |
| Office delivery openability and content completeness | `missing` | Blocks acceptance. No Office file is uploaded, read, parsed, generated, or verified by 2.10.2. |
| Visual render, layout, and readability | `missing` | Blocks acceptance. No screenshot, render, or visual evaluation is captured or claimed by 2.10.2. |
| Human acceptance decision | `not_recorded` | Blocks acceptance until a separate, attributable review record exists. |

Consequently each persisted draft remains `acceptance_status=hold`, `blocking_status=blocked`, `production_status=not_authorized`, and `release_impact=none`. `can_auto_accept`, `can_auto_execute`, and `can_auto_approve_release` are all permanently initialized as `false` in this slice.

## Included and excluded decision context

The review templates bind only to the four separately materialized `2.10.1` packets:

| Context card | Decision | 2.10.2 review draft |
| --- | --- | --- |
| WorkBuddy controlled external-result return boundary | `integrate` | Controlled external-result return boundary review |
| Editable deliverables and source lineage | `build` | Editable deliverable lineage review |
| Consent-scoped project context and change preview | `build` | Context/change-preview review |
| Desktop automation safety prerequisites | `defer` | Deferred desktop-automation safety review |

TRAE autonomous IDE execution and QClaw instant-message local-device execution remain explicitly excluded. No 2.10.2 route adds a connector call, file write, device action, or desktop automation capability.

## Review and revision contract

- The `POST /api/product-strategy/artifact-acceptance/initialize` operation is explicit and idempotent.
- It returns `409 decision_context_packets_required` until the four 2.10.1 packets have been initialized independently. It never initializes those prerequisites automatically.
- Each draft binds the context-packet key, source references, source digests, packet revision/digest, and an evidence-source-bundle digest.
- Each initial revision stores an immutable snapshot and a field-level diff with `before`, `after`, and change type. The diff itself declares `auto_acceptance_forbidden=true` and `release_gate_mutated=false`.
- Re-running initialization preserves human-managed drafts and revisions rather than overwriting them.
- The user instruction recorded here has scope `artifact_acceptance_definition_only`; it is not a named reviewer identity, artifact acceptance decision, execution authorization, or release approval.

The available API surface is:

- `GET /api/product-strategy/artifact-acceptance/preview` — static, database-free HOLD-only preview;
- `GET /api/product-strategy/artifact-acceptance` — persisted drafts and prerequisite readiness only;
- `POST /api/product-strategy/artifact-acceptance/initialize` — explicit materialization after 2.10.1, never acceptance.

The `/competitive` workspace presents the same state and requires an in-browser confirmation before initialization.

## Verification completed locally

- Isolated service/API tests verify the prerequisite failure, idempotent initialization, immutable revision/diff payloads, and preservation of human-managed records.
- Fresh SQLite Alembic upgrade to `20260828_0033`, downgrade to `20260828_0032`, and `Base.create_all` followed by upgrade were verified.
- Targeted frontend API/component tests passed with the backend contract.

These checks validate the software contract. They do not supply the missing Office, visual, or human-review evidence.

## Next evidence-bearing action

A later, separately authorized iteration may attach real Office round-trip material, visual render captures, and attributable human review records to a defined artifact. Before that work is accepted, it must preserve the current release-evidence chain and must not change `baseline_hybrid` or the blocked release-readiness state.
