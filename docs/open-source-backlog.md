# Open Source Backlog

This file is the contributor-friendly backlog for the public Anti-FOMO repository.

It focuses on work that is:

- easy to understand from product and code context
- small enough for outside contributors to pick up
- useful for collection quality, research workflow, or onboarding

## Good first issue

### 1. Add a Chinese contributor quickstart

- Area: docs / onboarding
- Labels: `good first issue`
- Why it matters:
  - The current repository is approachable, but Chinese-speaking contributors would benefit from a faster local setup and release-check guide.

## Medium scope roadmap items

### 2. Better demo and sample data packaging

- Area: demo workflow
- Why it matters:
  - Stronger sample data and demo setup would make the repo easier to evaluate without personal sources or private environments.

## Implemented public work

- [Visible data-source states](../src/lib/data-source-state.ts): Web Feed, Saved, and Item Detail share explicit live/degraded/empty/unavailable/demo language; the Mini Program mirrors it through [`miniapp/utils/data-source-state.js`](../miniapp/utils/data-source-state.js) and does not silently present local fixtures as live API data.
- [WeChat collector reliability evidence](./wechat-collector-reliability-benchmark.md): accessibility-first navigation, localized fallback, route diagnostics, and a deterministic perceptual-dedupe before/after packet with explicit synthetic/live-device boundaries.
- [`/competitive` evidence capture](./competitive-evidence-capture.md): repeatable desktop-browser and mobile-viewport PNG, GIF/MP4, manifest, and local browser-metric workflow.
- [Public roadmap](./public-roadmap.md): a stable repository-local orientation layer for research, collection, and execution themes; it preserves the existing evidence and release boundaries.
- [Product surface map](./product-surface-map.md): a compact matrix for collector, research, Focus, action cards, Mini Program, and browser-extension surfaces.
- [GitHub launch polish checklist](./github-launch-polish-checklist.md): a reusable public-repository checklist for social preview, pinned-repo copy, release links, and README assets.

These entries describe checked-in implementation or documentation. They do not imply physical-device, customer, Office, production, or release acceptance.

## Triage notes

When opening public issues, keep them:

- scoped to one user-visible outcome
- grounded in a concrete screen, route, or flow
- explicit about verification steps
- honest about whether the change is docs-only, frontend, backend, or collector-related
