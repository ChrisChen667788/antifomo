# 2.10.0 Competitive Capability Observatory

Status: `2.10.0-development` proposed and locally implemented as a product-strategy evidence slice. This document records a source-backed product comparison and the associated engineering boundary. It does not approve a release, a production strategy change, or a competitor capability claim beyond the linked first-party material.

Research date: `2026-08-28`

## Decision

Anti-FOMO should not chase a generic office agent, an IDE, or a broad connector marketplace. Its differentiated chain remains:

`reviewable source snapshot -> claim and evidence control -> Chinese decision document contracts -> architecture trade-offs -> executable acceptance evidence`

The first post-`2.9.5` engineering slice is therefore a Competitive Capability Observatory: a separately governed, source-backed ledger for competitor claims, product gaps, explicit non-goals, and proposed roadmap cards. It must keep three states separate:

| State | Meaning |
| --- | --- |
| `vendor_claim` | A capability stated in a linked first-party product source. It is not an independent benchmark result. |
| `local_implementation` | Code or a deterministic fixture exists in this checkout. It is not customer or production acceptance. |
| `release_blocked` | Existing human, security, performance, Office, visual, and release-evidence gates remain unsatisfied. No product roadmap card can override them. |

## Scope and Method

- Sources are first-party product pages or official documentation only.
- Each observation must carry a URL, observed date, canonical evidence-payload digest, evidence tier, and expiry date.
- An unavailable or missing source means `unknown`; an expired observation becomes `stale`. Neither state may be shown as proof that a competitor does not have a capability.
- A recommended capability must state the user problem, why it reinforces Anti-FOMO's differentiated chain, its code boundary, risk, measurable acceptance criterion, and a `build`, `integrate`, `defer`, or `explicitly_not_copy` decision.
- The comparison is a product/engineering decision aid. It is not market-share, pricing, security-certification, or hands-on performance research.

## Current Product Comparison

| Product | First-party observed strengths | Relevant lesson | Anti-FOMO decision |
| --- | --- | --- | --- |
| [Tencent WorkBuddy](https://intl.cloud.tencent.com/zh/products/workbuddy) | The product page publicly describes an office-oriented AI Agent workspace, task orchestration, office-tool connections, and result delivery. | A visible task lifecycle and result/provenance surface reduce the gap between request and delivery. | `integrate`: consider a controlled external-result return boundary only. `explicitly_not_copy`: unrestricted task execution before approvals, source admission, budgets, and rollback are proven. |
| [TRAE](https://docs.trae.cn/) | Official documentation presents an AI-native coding environment that uses repository context to assist development work. | Engineering changes benefit from scoped context and test feedback rather than an opaque agent run. | `explicitly_not_copy`: do not turn Anti-FOMO into an AI IDE or allow autonomous code/terminal execution. |
| [千问办公](https://qwenwork.cn/docs/product-introduction) | The product introduction publicly describes a natural-language office platform for document, data, and office deliverables. | Deliverables must remain editable, attributable, and reviewable after generation. | `build`: evidence-bound artifact lineage and revision history; do not claim product interoperability or copy an office suite. |
| [LangHub](https://www.langhub.cn/?locale=zh) | The product page publicly emphasizes a context workspace with tool-chain, intent, and validation alignment. | A product decision should retain its source context and rationale without asking users to restate it. | `build`: bounded, reviewable project context and change preview; no silent cross-project memory. |
| [百度 Dumate](https://cloud.baidu.com/doc/Dumate/index.html) | Official documentation describes a desktop office agent for local file, data, and automation tasks. | Desktop automation needs directory-scoped permissions, dry runs, and explicit confirmation. | `defer`: no desktop control or arbitrary file write until a separate safety design and evidence set is accepted. |
| [腾讯 QClaw](https://intl.cloud.tencent.com/zh/document/product/1300/81043) | Official documentation describes a local AI Agent that can receive remote tasks through an instant-messaging entry point. This is the likely product referred to as "腾讯兔子" in the historical request; the original wording is retained as a traceability note. | Remote control magnifies approval, identity, and audit requirements. | `explicitly_not_copy`: do not allow instant messages to remotely execute local-device actions. |

The claims in this table are vendor statements, not independent comparative measurements. The product names and source links are intentionally stored as evidence rows in the 2.10.0 API rather than being treated as unqualified feature facts.

## Product Gaps and Proposed Backlog

| Candidate | Decision | Why it fits the product | Acceptance boundary |
| --- | --- | --- | --- |
| `2.10.0` Competitive Capability Observatory | `build` | Turns ad-hoc competitor research into an evidence-bound, refreshable decision surface with clear non-goals. | Every rendered competitor claim has a first-party source, observed timestamp, digest, evidence tier, and expiry; roadmap cards cannot become approved automatically. |
| `2.10.1` [Reviewable decision context packets](reviewable-decision-context-packets-v2.10.1.md) | `build` | Retains problem, source bundle, assumptions, owner, constraints, and prior decision without unbounded memory. | No context crosses product-strategy projects without an explicit link; every generated decision cites its packet revision. |
| `2.10.2` [Artifact acceptance and revision diff](artifact-acceptance-and-revision-diff-v2.10.2.md) | `defer` for acceptance, locally implemented as a HOLD-only review control plane | Brings the editable-deliverable lesson into evidence-bound DOCX/PPTX work without copying an office suite. | Needs independent Office/visual evidence and an attributable human decision; unsupported values, claims, and formula changes remain blocked. |
| `2.10.3` Approved execution proposals | `defer` | Allows WorkBuddy/Dumate/QClaw-style task value only through scoped, reviewable execution plans. | Needs signed Skills, permissions, dry runs, exact human approval, idempotency, replay, and rollback proof. |
| `2.10.4` Product-strategy source change review | `build` after 2.10.0 review | Makes freshness visible and turns changed official claims into a review queue rather than silent roadmap churn. | No source refresh overwrites a human decision; expired observations become `stale` and retrieval failures become `unknown`. |

## Existing Release Boundary

This roadmap does not change the current `2.9.5` release state. The fixed retrieval cohort is still partial, the configured Cross Encoder is not applied when its external cache is unavailable, and the recorded human-review material is not a current completed protocol. Therefore:

- `baseline_hybrid` remains the only production default.
- Existing release-readiness remains `blocked`.
- A bundled competitor source, a generated template, or a local test cannot count as external approval.
- Any follow-on capability must preserve the current fail-closed source, claim, permission, and delivery gates.

## Implementation Boundary

The code is isolated under `product_strategy` rather than folded into customer/tender `market_intelligence` or the existing Research Center assurance panels.

- Backend: product-strategy models, schema, service, API router, and migration `20260828_0031`.
- Frontend: `/competitive` with a dedicated evidence and roadmap workspace.
- Persistence: official-source snapshots and decision cards are initialized idempotently; initialization never overwrites a human-edited record.
- Refresh: the current implementation reports freshness from stored observation/expiry fields. It does not scrape, trust, or publish a changed third-party page automatically.

## Source Register

1. [Tencent WorkBuddy product page](https://intl.cloud.tencent.com/zh/products/workbuddy)
2. [TRAE documentation](https://docs.trae.cn/)
3. [千问办公 product introduction](https://qwenwork.cn/docs/product-introduction)
4. [LangHub product page](https://www.langhub.cn/?locale=zh)
5. [百度 Dumate documentation](https://cloud.baidu.com/doc/Dumate/index.html)
6. [Tencent QClaw documentation](https://intl.cloud.tencent.com/zh/document/product/1300/81043)

## 2026-08-31 Follow-on

The governed follow-on train is documented in [Anti-FOMO 国内外模型 / Agent 竞品分析与 15 版本迭代方案](competitive-agent-landscape-and-iteration-program-2026-08-31.md). The 2.10.3–2.11.7 local control plane, fresh official Agent register and weekly source-change monitor extend this ledger without rewriting its historical observations. All new vendor claims remain unverified, all fifteen iterations remain `HOLD`, and the release gate is unchanged.
