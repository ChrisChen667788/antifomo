# Anti-FOMO Current Product Status

Updated: 2026-10-02

This is the canonical status page for public documentation. The repository is an active local-first development prototype. A working route, test result, preview, or generated artifact does not by itself establish production readiness, customer acceptance, or a signed commercial deployment.

## Current line

- **Implemented development line:** `2.10.3–2.11.8-development`.
- **2.12.0 status:** PR-A Task Envelope schema/state is tracked in [GitHub PR #12](https://github.com/ChrisChen667788/antifomo/pull/12) as `local_implementation`. Merging this code does not make it a released 2.12.0 line. The execution flag defaults off, and PR-A has no executor or callback sender.
- **Release baseline:** `baseline_hybrid`.
- **Release promotion:** `blocked` until independent retrieval review, human review/qrels, expert calibration, blind evaluation, customer acceptance, production Skill/connector governance, and final Office/visual/security/performance/recovery evidence are complete.
- **Evidence control plane and launch kit:** [PR #11](https://github.com/ChrisChen667788/antifomo/pull/11). Its GitHub status records the merge outcome; source-code integration into `main` is separate from release or production approval.
- **Source-monitor snapshot:** The [2026-09-22 review packet](./competitive-source-review-2026-09-22.md) records 12 successful local captures, one failed capture and the remaining source-by-source assessment in [issue #10](https://github.com/ChrisChen667788/antifomo/issues/10). Fresh source observations do not accept historical claims or changed comparison baselines.
- **Verified CI snapshot:** [Run 35721207545](https://github.com/ChrisChen667788/antifomo/actions/runs/35721207545) passed `check`, `smoke`, and `focus-e2e` for commit `42bfd23`. Consult the PR checks for later commits; this result does not approve a release.

## Evidence legend

| Label | Meaning |
| --- | --- |
| `local_implementation` | Code exists in this checkout and has a reproducible test or inspection path. |
| `demo` | A local route, fixture, screenshot, animation, or preview demonstrates a path. |
| `synthetic_benchmark` | A fixed or generated dataset/benchmark result; it is not a customer or production metric. |
| `vendor_claim` | A product/vendor page or investor communication claim. |
| `human_acceptance` | An attributable reviewer accepted a specific version and artifact. |
| `customer_acceptance` | A named customer accepted a scoped pilot or production artifact. |
| `production` | A deployed system with an agreed operational boundary and measured service evidence. |

Marketing pages must name the highest applicable label beside every metric or outcome claim.

## Surface status

| Surface | Status | Evidence boundary |
| --- | --- | --- |
| WeChat/web/file intake and source diagnostics | `local_implementation` + `demo` | Collector fixtures, tests, and local screenshots; third-party source availability varies. |
| Retrieval, evidence ledger, compare and report workflow | `local_implementation` + `demo` | Local tests and evidence receipts; independent retrieval/customer review remains open. |
| Architecture readiness and solution architect workbench | `local_implementation` + `demo` | Generated blueprints and UI paths; not a customer-approved architecture. |
| Office/visual evidence receipts | `local_implementation` | Local hashes and render receipts; they do not replace named human/customer acceptance. |
| Task Envelope PR-A schema/state subset | `local_implementation` | Proposal, frozen digest, budget/scope digest binding, append-only approval/receipt, revocation and model-profile contracts exist in the local API. PR-A has no executor; the reserved execution flag defaults off but does not gate proposal/control calls. Approver, actor and scope values are caller-supplied strings without a trusted identity or permission policy, so an `approved` record is not proof of human authorization. |
| WorkBuddy bridge | `local_implementation` | Local compatibility webhook and CodeBuddy CLI bridge. Signature checking is conditional: an empty secret bypasses it. The webhook directly executes supported export task types and can send a result to a request-supplied or configured callback URL. There is no universal human-approval gate; health/CLI detection does not prove native Tencent WorkBuddy interoperability. |
| Animated marketing assets | `demo` | Conceptual SVG plus a historical local-UI screenshot montage. Asset manifests identify source version and render provenance; neither is live telemetry or evidence of the current release's behavior. |

## Visual evidence status

- `docs/assets/screenshots/screenshot-manifest.json` now records 34 light/dark local browser captures for 17 surfaces from source commit `10b536c`. PNG hashes, dimensions, required content, theme state, and browser diagnostics passed against an isolated database copy. `human_visual_review_status` remains `pending`, so this does not clear the visual release gate.
- `docs/assets/competitive-evidence/competitive-evidence-manifest.json` now records the 16-version / 7-source read-only preview from source commit `ccbf836`, with seven PNG captures, three browser-navigation samples per viewport, and a four-second GIF/MP4. File hashes and monitored browser diagnostics passed; simulated mobile CSS viewports are not physical-device evidence, performance samples are local rather than production, and `human_visual_review_status` remains `pending`.
- `docs/product-whitepaper.md`, README files, launch copy, and roadmap should link this page rather than inventing separate “current version” sentences.

## Next decision

The next implementation step is PR-B: adapt the WorkBuddy webhook, `POST /api/tasks`, and Focus Assistant action path to create proposals, register callback intent without secrets, and fail closed until a current approval passes an authenticated permission policy. PR-C then updates the Web surfaces for proposal/review/receipt states. The [ten-version engineering plan](./workbuddy-integration-plan-2026-09-18.md) and [WorkBuddy research report](./workbuddy-deep-dive-2026-09-18.md) remain the governing scope. New planner, connector, scheduler and desktop-action paths must remain read-only proposal or fail-closed until their version gates pass. The legacy export paths still retain direct execution, and WorkBuddy retains its conditional signature check and callback behavior, so PR-A and 2.12.0 as a whole are not complete.
