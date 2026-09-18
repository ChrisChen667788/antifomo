# Anti-FOMO Current Product Status

Updated: 2026-09-18

This is the canonical status page for public documentation. The repository is an active local-first development prototype. A working route, test result, preview, or generated artifact does not by itself establish production readiness, customer acceptance, or a signed commercial deployment.

## Current line

- **Implemented development line:** `2.10.3–2.11.8-development`.
- **Release baseline:** `baseline_hybrid`.
- **Release promotion:** `blocked` until independent retrieval review, human review/qrels, expert calibration, blind evaluation, customer acceptance, production Skill/connector governance, and final Office/visual/security/performance/recovery evidence are complete.
- **Latest governed PR:** [#11](https://github.com/ChrisChen667788/antifomo/pull/11), draft, branch `codex/governed-evidence-control-plane`.
- **Latest source-monitor run:** GitHub Actions run [35352638150](https://github.com/ChrisChen667788/antifomo/actions/runs/35352638150), a read-only official-source monitor. It is research evidence, not release approval.

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
| WorkBuddy bridge | `local_implementation` | Health detection and controlled export/CLI bridge; it is not Tencent-hosted WorkBuddy execution. |
| Animated marketing assets | `demo` | Deterministic, source-controlled SVG/frames; not a live telemetry or production performance view. |

## Known documentation drift

- `docs/assets/screenshots/screenshot-manifest.json` remains a historical `v1.9.1` screenshot baseline; it must not be used as evidence for the current version.
- `docs/assets/competitive-evidence/competitive-evidence-manifest.json` was captured before the `2.11.8` extension and still reports a 15-slice preview. A fresh capture must update the manifest before marketing claims the 16-slice visual evidence is current.
- `docs/product-whitepaper.md`, README files, launch copy, and roadmap should link this page rather than inventing separate “current version” sentences.

## Next decision

The next product decision is whether to implement the controlled execution lane described in [the marketing and WorkBuddy integration plan](./marketing-overhaul-2026-09.md). The default remains read-only proposal, human review, fail-closed execution, and reversible local evidence until the corresponding version gates pass.
