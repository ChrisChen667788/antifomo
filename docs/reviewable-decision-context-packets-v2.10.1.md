# 2.10.1 Reviewable Decision Context Packets

Status: `2.10.1-development` locally implemented and validated. It is not a release, production, execution, or customer-acceptance approval.

`approved_for_context` means only that the explicitly approved product decision may be persisted as a bounded, reviewable design context. It does not permit a release, a production-retrieval change, an external connector call, a file write, or a device action; it also does not satisfy any `2.9.5` release-evidence gate.

## Explicit product decision

On `2026-08-28`, the product owner explicitly instructed Anti-FOMO to let the `build`, `integrate`, and `defer` decisions from the 2.10.0 Competitive Capability Observatory enter the next design stage. That instruction is recorded as product-strategy approval evidence only. It is deliberately not represented as a named external reviewer, a release approver, or an authorization to run an action.

The included cards are:

| Card | Decision | 2.10.1 treatment |
| --- | --- | --- |
| WorkBuddy controlled external-result return boundary | `integrate` | Package the allowlist, provenance, failure-closed, and human-review constraints. |
| Editable deliverables and source lineage | `build` | Package lineage, revision, unsupported-claim, and permission constraints. |
| Consent-scoped project context and change preview | `build` | Package scope, retention, preview, confirmation, and revocation constraints. |
| Desktop automation | `defer` | Retain the safety prerequisites and an explicit non-implementation boundary. |

The `explicitly_not_copy` cards remain excluded: Anti-FOMO does not gain AI IDE autonomous writing/terminal execution from TRAE, nor instant-message-triggered local-device execution from QClaw.

## Packet contract

Every persisted packet binds the following to one roadmap-card key and source digest:

- problem and decision rationale;
- source bundle and evidence digest;
- assumptions, constraints, owner scope, retention time, and revision digest;
- the explicit user-instruction approval evidence and an append-only initialization/revision audit record;
- `can_auto_execute=false`, `can_auto_approve_release=false`, and `requires_human_change_approval=true`.

No packet can cross product-strategy projects silently. A later change must produce a human-reviewed revision rather than mutating the approved context in place, and the new revision must bind its predecessor revision digest plus the source-catalog digest.

## Workflow

1. A read-only preview projects the four allowed packets and the two excluded cards from the 2.10.0 catalog.
2. An explicit, idempotent initialization materializes those four packets and their user-instruction audit evidence.
3. Human-maintained records are preserved; a later seed cannot overwrite them.
4. The persisted view exposes the packet/revision/source digests and all three hard gates for review.

The current local API is `GET /api/product-strategy/decision-context-packets/preview`, `GET /api/product-strategy/decision-context-packets`, and the explicit `POST /api/product-strategy/decision-context-packets/initialize`. The `/competitive` workspace requires an in-browser confirmation before it issues the POST.

## Release boundary

This version does not alter `baseline_hybrid`, retrieval behavior, release-readiness, or any 2.9.5 evidence gate. The existing fixed cohort, Cross Encoder, human-review, shadow, drift, rollback, and independent-audit requirements remain separate and fail closed.

## Follow-on boundary

The next possible work is a reviewable revision workflow for a packet, not automatic execution. `2.10.2` [artifact acceptance and revision diff](artifact-acceptance-and-revision-diff-v2.10.2.md) is now locally implemented as a HOLD-only control plane; it still requires the existing Office, visual, and human-review evidence before any artifact can be accepted.
