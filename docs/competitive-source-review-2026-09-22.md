# Official-source review packet — 2026-09-22

This packet addresses [Issue #10](https://github.com/ChrisChen667788/antifomo/issues/10). It records an agent-assisted inspection of the 13 official sources and the monitor's reproducible fetch result. It is **not a human semantic sign-off**, an independent product benchmark, a roadmap approval or a release approval.

## What changed

The previous register had one shared observation date (`2026-08-31`) and expiry (`2026-09-14`). The monitor also overwrote any per-source dates with these defaults. Every subsequent run therefore showed all 13 sources as stale, even after a successful new fetch.

The register now records a dated `observation_snapshot` for each source. The 12 successful Node fetches have their own observation window, from `2026-09-22T11:57:49.761Z` to `2026-10-06T11:57:49.761Z`. The failed Google fetch retains its historical observation dates. Source-level dates take precedence over the fallback dates.

These dates concern source availability only. All 13 historical claims retain their original dates inside `semantic_review`, all 13 comparison baselines remain unchanged, and `reviewed_by` / `reviewed_at` remain `null`. Pending semantic review stays visible even when a source hash is unchanged. No vendor claim, local comparison, build/integrate/defer decision or release gate was changed to clear the alert.

The monitor also counts an unset baseline independently of fetch success. This prevents a failed Google fetch from hiding the already-known missing baseline. The workflow links this packet from its issue body so each recurring alert has an actionable reference.

## Reproducible capture

- [Original Node observation report](./competitive-reviews/2026-09-22-observation-report.json)
- Generated: `2026-09-22T11:57:49.761Z`
- Report digest: `e5f0e803f215ab09337c002023e31953e221a8fc51206eede71967c2691f531e`
- Result: 12 fetched, 1 failed; 9 changed, 3 unchanged, 1 unknown against the **historical** comparison baselines.
- Google has an unset baseline. A separate web read was possible; it does not replace a successful Node capture or supply a compatible hash.

The capture stores source metadata and hashes rather than reproducing full third-party pages. Normalization removes HTML markup, scripts, styles and repeated whitespace; navigation or template changes can still change a digest. `content_changed` is therefore a review signal, not proof that a product capability changed. The observed pages and semantic interpretations below remain vendor-source evidence.

## Source-by-source findings

| Source | Node capture / historical hash | Current inspection and action required |
| --- | --- | --- |
| [WorkBuddy](https://www.workbuddy.cn/docs/workbuddy/Overview) | fetched / changed | The overview still describes natural-language tasks, planning, office artifacts and authorized local-file access. Navigation also exposes Enterprise, Buddy Apps, team collaboration and automation. Reconcile the older broad comparison with the [2026-09-18 deep dive](./workbuddy-deep-dive-2026-09-18.md); keep desktop, enterprise and CLI scopes separate. |
| [TRAE](https://docs.trae.cn/) | fetched / changed | The overview now distinguishes TraeCode, TraeWork, Plugin, CLI and Enterprise. TraeWork includes office, code and design modes. The historical IDE-only scope is incomplete; split product surfaces before reconsidering the existing `explicitly_not_copy` decision. The documented Node user-agent fetched content; a generic fetch returned a user-agent rejection and is not an accepted source. |
| [QwenWork](https://qwenwork.cn/docs/product-introduction) | fetched / changed | The introduction still describes office artifacts and DingTalk integration; it also lists cloud scheduling and client browser automation. Review these extensions and their client boundaries. They do not establish an Anti-FOMO connector or measured delivery quality. |
| [LangHub](https://www.langhub.cn/?locale=zh) | fetched / unchanged | Persistent context, planning, change preview and rollback remain stated. No normalized content change was detected. A reviewer still needs to renew the expired claim assessment; unchanged text is not renewed trust. |
| [DuMate](https://cloud.baidu.com/doc/Dumate/index.html) | fetched / changed | The main description still covers desktop file handling, data processing and office automation. Navigation now uses “百度搭子” alongside the Dumate title. Reconcile naming and product scope; do not infer a capability change only from a template digest. |
| [QClaw](https://intl.cloud.tencent.com/zh/document/product/1300/81043) | fetched / changed | This official TokenHub configuration guide still describes OpenClaw-based local tasks and a WeChat entry point. Keep configurable models separate from product claims. The vendor's safety/local-data wording is not an independent security assessment. |
| [Codex CLI](https://raw.githubusercontent.com/openai/codex/main/README.md) | fetched / unchanged | The monitored README supports local coding-agent and IDE/app/web entry observations. It does **not** establish the historical register's GPT model names, scheduling breadth or comparative superiority. Add appropriate official product/model references before renewing those statements; do not treat this CLI snapshot as coverage of every Codex surface. |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started) | fetched / changed | The legacy URL redirects to [Advanced setup](https://code.claude.com/docs/en/getting-started). Setup, terminal and deployment context are visible, but this page does not establish the historical “strongest model” statement. The canonical destination is retained in observation provenance; model claims require their own source. |
| [Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agents) | failed / unknown; baseline unset | The Node monitor failed locally. An independent web read reached the official overview dated 2026-09-21 and found lifecycle, identity, registry, governance and observability descriptions. Keep the monitor failure and missing baseline unresolved until the same monitor can capture it. The overview does not establish the register's specific Gemini model names. |
| [Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio) | fetched / changed | The root resolves to the [en-us documentation](https://learn.microsoft.com/en-us/microsoft-copilot-studio/) with creation, evaluation, publishing, monitoring and governance. Current docs distinguish GitHub Copilot and standard harness paths; review scope and preview labels before renewing comparison claims. |
| [Qwen-Agent](https://raw.githubusercontent.com/QwenLM/Qwen-Agent/main/README.md) | fetched / unchanged | The framework, tools, planning, memory and February 2026 Qwen3.5 examples are still present. The README now describes a Docker-based code interpreter and continues to caution about production. A warning attached to an older unsandboxed example must not be generalized to all current executors. |
| [Coze](https://docs.coze.cn/what_is_coze) | fetched / changed | The current introduction centers on team collaboration with projects, multiple agents, files/assets and persistent task context. Separate Coze collaboration from Coze Coding; the old code/preview/deployment-centered description is incomplete. Reassess the scope before changing the existing decision. |
| [Manus API v2](https://open.manus.ai/docs/v2/introduction) | fetched / changed | Tasks, shared project instructions, files, webhooks and skills are still described. The page also lists custom agent management and says API v1 is deprecated. Keep API v2 scope explicit and do not infer task success, safety or account integration from documentation. |

## Remaining review checklist

Issue #10 should stay open until the following work has attributable review records. The source-fetch repair can be merged independently.

- [ ] Resolve the Google monitor failure and capture a compatible baseline. A successful CI fetch can establish availability; a named reviewer must accept the baseline after checking its content.
- [ ] Review the scope changes in TRAE / TraeWork and Coze / Coze Coding; choose which product surfaces the existing decisions cover.
- [ ] Verify or withdraw the dated model statements for Codex, Claude and Gemini using model-specific official references. The current monitored pages are insufficient.
- [ ] Review the WorkBuddy, QwenWork, DuMate, QClaw, Copilot Studio and Manus changes; distinguish substantive capability changes from navigation/template changes.
- [ ] Renew semantic assessment for unchanged LangHub, Codex CLI and Qwen-Agent content; confirm each local comparison remains appropriately qualified.
- [ ] Record reviewer identity, review date, scope and accepted digest for each source. Update a comparison baseline only with that review; retain the prior capture as history.

The human-review requirement comes from the repository register's `human_semantic_review_required` methodology. It is not fulfilled by this agent-generated packet, an HTTP 200, a matching hash or a user request to triage issues. The packet deliberately provides no invented human reviewer or external acceptance.

## Validation and next run

```sh
npm run competitive:monitor:test
npm run competitive:monitor -- --output-dir output/competitive-monitor
```

Four monitor tests cover legacy date fallback, a missing baseline during fetch failure, source-level date precedence, unchanged content with pending semantic review, changed baseline preservation, and failed-source `unknown` behavior. The live run remains review-required by design. Once this change reaches the default branch, rerun the GitHub workflow there and use its report digest and source matrix for the issue update; local network failure must not be presented as the CI result.
