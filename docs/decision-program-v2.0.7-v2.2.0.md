# Decision Program 2.0.7-2.2.0

Development baseline: `2.2.0+20260718`

Engineering status: `implemented`.

Commercial acceptance status: `blocked` until the named independent, expert, production, Office/visual, security, vertical-pack, and customer artifacts are submitted and pass against immutable digests.

## Implemented Versions

| Version | Runtime contract | Primary API |
| --- | --- | --- |
| `2.0.7` | Immutable release candidate with digest preview, one validation run per suite, matching digest checks, external attestations and blocker snapshot | `POST /api/decision-studio/program/release-candidates/preview`, `/release-candidates` |
| `2.1.0` | Draft/revise/approve research plan, frozen accepted-source revisions, budget, checkpoint, pause/resume/cancel/complete and comparison | `/api/decision-studio/program/research-runs` |
| `2.1.1` | Semantic, lexical and hybrid-RRF retrieval plus immutable retrieval/parser/model/vertical benchmark evidence | `/api/decision-studio/notebooks/{id}/search`, `/program/quality-benchmarks` |
| `2.1.2` | Claim/section-backed blocks, optimistic revision lock, human-edit preservation, differential rebuild, DOCX/PPTX and independent visual confirmation | `/api/decision-studio/program/document-drafts` |
| `2.1.3` | HTTPS identity providers with client fingerprint only, tenant role mapping, Microsoft 365/SharePoint connectors and idempotent ACL sync snapshots | `/api/decision-studio/program/identity-profiles`, `/program/connectors/{id}/sync` |
| `2.1.4` | Approved Skill-backed Agent runs with plans, schedules, budgets, checkpoints, exact high-risk approvals, pause/resume/cancel and safe internal rollback | `/api/decision-studio/program/agent-runs`, `/program/agent-approvals/{id}` |
| `2.1.5` | Immutable medical, finance and tourism packs with official-source registries, ontologies, contracts, hard negatives, rubrics and licensing controls | `/api/decision-studio/program/vertical-packs` |
| `2.2.0` | Space-bound customer Pilots with deployment/SLA profile, full workflow evidence, inherited 2.0.7 readiness and named customer signoff | `/api/decision-studio/program/customer-pilots` |

## Persistence

Migration `20260718_0028_add_decision_program.py` adds ten tables for release candidates, research runs, quality benchmarks, document drafts, identity profiles, connector sync runs, Agent runs/approvals, vertical packs and customer Pilots. Immutable versions use unique digests or idempotency keys; mutable workflows retain revisions, checkpoints and audit events.

## Frontend

`/studio` adds a `版本收口` tab with the eight-version engineering/acceptance matrix, immutable RC freeze action and vertical-pack status. Evidence search exposes semantic, hybrid RRF and lexical modes. The existing release-readiness tab remains separate so a locally implemented capability cannot hide a missing external gate.

## Acceptance Boundary

The runtime intentionally remains blocked when any of these are absent:

- all existing validation suites bound to one `2.0.7` candidate digest;
- expert calibration, three-industry blind review and named customer acceptance artifacts;
- 600 adjudicated qrels and 200 real parser/click-back documents;
- independent Office visual confirmation for the exact export digest;
- production identity/ACL/revocation/connector failure matrix;
- at least 100 adversarial Agent cases with no undeclared or duplicate effects;
- at least 100 tasks and 30 real expert artifacts for each vertical pack;
- accepted customer Pilots covering medical, finance and tourism.

Fixtures and local unit tests validate the contracts only. They are never counted as external acceptance.
