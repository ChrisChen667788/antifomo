# Anti-FOMO Current Product Status

Updated: 2026-09-22

This is the canonical status page for public documentation. The repository is an active local-first development prototype. A working route, test result, preview, or generated artifact does not by itself establish production readiness, customer acceptance, or a signed commercial deployment.

## Current line

- **Implemented development line:** `2.10.3–2.11.8-development`.
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
| WorkBuddy bridge | `local_implementation` | Local compatibility webhook and CodeBuddy CLI bridge. Signature checking is conditional: an empty secret bypasses it. The webhook directly executes supported export task types and can send a result to a request-supplied or configured callback URL. There is no universal human-approval gate; health/CLI detection does not prove native Tencent WorkBuddy interoperability. |
| Animated marketing assets | `demo` | Conceptual SVG plus a historical local-UI screenshot montage. Asset manifests identify source version and render provenance; neither is live telemetry or evidence of the current release's behavior. |

## Known documentation drift

- `docs/assets/screenshots/screenshot-manifest.json` remains a historical `v1.9.1` screenshot baseline; it must not be used as evidence for the current version.
- `docs/assets/competitive-evidence/competitive-evidence-manifest.json` was captured before the `2.11.8` extension and still reports a 15-slice preview. A fresh capture must update the manifest before marketing claims the 16-slice visual evidence is current.
- `docs/product-whitepaper.md`, README files, launch copy, and roadmap should link this page rather than inventing separate “current version” sentences.

## Next decision

The next implementation sequence adds an envelope/provenance/approval layer around the existing export bridge, then builds the controlled execution lane in the [ten-version engineering plan](./workbuddy-integration-plan-2026-09-18.md). The [WorkBuddy research report](./workbuddy-deep-dive-2026-09-18.md) records the comparison and its sources. These follow-on versions are planned, not implemented by this documentation refresh. New planner, connector, scheduler and desktop-action paths must remain read-only proposal or fail-closed until their version gates pass. The legacy export route retains its conditional signature check, direct execution and callback behavior until the planned migration closes those gaps.
