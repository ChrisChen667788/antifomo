# Contributing

[English](./CONTRIBUTING.md) · [简体中文](./CONTRIBUTING.zh-CN.md)

Start with one concrete friction point: a source that fails, a citation that cannot be checked, a confusing export, or a repeated manual step. Describe the expected result and include a small public or synthetic example. You can suggest an approach in an issue before writing code.

## Development Setup

1. Install Node.js 20+ and Python 3.11, with `python3.11` on your PATH.
2. Run `npm run demo:setup` and `npm run demo:start` as described in the [Quick Start](./README.md#quick-start).
3. Use public or synthetic data. Configure only the external services needed for the affected flow.

## Before Opening a PR

- Explain the user-visible change, its scope, and how you verified it.
- Run relevant checks. `npm run check` runs the full local suite after setup; documentation-only changes need link/render verification, and should state that product tests were not rerun.
- For UI changes, show the affected state and viewport; for backend changes, include failure and recovery cases relevant to the behavior.
- Keep `.env`, `.tmp`, databases, customer data, Mini Program `AppID`, credentials and local build artifacts out of Git.

## Scope

High-value contributions for this repository:

- content intake and collector reliability
- research quality and citation grounding
- focus/session artifact quality
- mini program and extension integration
- tests, CI, and packaging improvements
- accessible diagrams, localized copy and reproducible marketing assets

The [backlog](./docs/open-source-backlog.md) lists small entry points. The [WorkBuddy integration plan](./docs/workbuddy-integration-plan-2026-09-18.md) breaks future `2.12.0–2.21.0` work into PRs with dependencies and acceptance criteria. Link the specific slice you propose to take on; the plan's performance budgets are targets, not measured guarantees.

## Reviewing evidence and marketing

Use the [current product status](./docs/current-product-status.md) to distinguish code, demos, benchmarks and external acceptance. Marketing screenshots must identify their capture version. Research contributions should include the direct source URL, observation date, exact supported claim and unresolved limitations. A new vendor page observation does not automatically renew the source register or approve a release.

The active [PR #11](https://github.com/ChrisChen667788/antifomo/pull/11) accepts review comments and suggested changes. Fork the repository and submit a focused PR for code contributions. Merge and release remain separate review decisions.
