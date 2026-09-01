# Anti-FOMO Product Surface Map

Anti-FOMO is one workflow with several entry points, not six disconnected products. This matrix helps a new user choose the correct surface and helps a contributor find the first code or documentation boundary to inspect.

## Comparison matrix

| Surface | Primary job | Entry point | Typical input -> output | State and provenance cues | First place to inspect |
| --- | --- | --- | --- | --- | --- |
| Collector | Bring web, WeChat, file, newsletter, RSS, and transcript signals into a recoverable intake path. | Web: [`/collector`](../src/app/collector/page.tsx) | URL, file, screenshot, source config -> item, source-health diagnostic, retry/export record. | Show the collection route, body/source status, retries, source health, and whether OCR or another fallback was used. | [`backend/app/api/collector_operations.py`](../backend/app/api/collector_operations.py), [`scripts/`](../scripts/) |
| Research workspace | Turn admitted source material into an evidence-aware report, comparisons, and reviewable delivery context. | Web: [`/research`](../src/app/research/page.tsx) | Research question + scoped sources -> report, evidence diagnostics, topic version, watchlist/archive. | Report and retrieval surfaces distinguish source/evidence readiness from formal delivery approval. | [`src/components/research/`](../src/components/research/), [`backend/app/api/research.py`](../backend/app/api/research.py) |
| Focus | Reserve a bounded working session and return its results to the same research loop. | Web: [`/focus`](../src/app/focus/page.tsx) | Goal + duration -> session state, collector handoff, summary and follow-up. | Local timer, connected collector, and recoverable session state must remain visible rather than silently implying a completed backend action. | [`src/components/focus/`](../src/components/focus/), [`src/lib/focus-runtime-model.ts`](../src/lib/focus-runtime-model.ts) |
| Action cards and delivery outputs | Convert reviewed research into next-step material for owners and stakeholders. | Web: Research and [`/session-summary`](../src/app/session-summary/page.tsx) | Report/session -> action cards, briefs, follow-up draft, watchlist digest, formal-export candidate. | An action card is a proposal or task aid; it is not proof of task execution, customer acceptance, or release approval. | [`src/lib/research-action-cards.ts`](../src/lib/research-action-cards.ts), [`src/components/research/research-action-cards-panel.tsx`](../src/components/research/research-action-cards-panel.tsx) |
| WeChat mini program | Provide mobile-side capture, review, focus, and knowledge access when the Mini Program environment is available. | [`miniapp/`](../miniapp/) | Mobile capture or feedback -> API request, offline queue, visible local/demo fallback, sync attempt. | The Mini Program explicitly labels local demo/mock mode and queued/offline actions; it cannot itself run a 24x7 desktop WeChat collector. | [`miniapp/README.md`](../miniapp/README.md), [`miniapp/pages/collector/`](../miniapp/pages/collector/) |
| Browser extension | Send the currently viewed browser page into the Anti-FOMO collection path. | [`browser-extension/chrome/`](../browser-extension/chrome/) | Current browser page -> quick-send collection request. | The extension is a collection entry point, not a substitute for source validation or research acceptance. | [`browser-extension/README.md`](../browser-extension/README.md), [`browser-extension/chrome/manifest.json`](../browser-extension/chrome/manifest.json) |

## Handoff chain

1. Use **Collector** or the **browser extension** to create an item with a traceable intake path.
2. Review it in the web workspace or **mini program**, where an unavailable backend or local demo path should be shown explicitly.
3. Use **Research** to form a source-aware report and compare changes over time.
4. Use **Focus** and **action cards** to turn an accepted next step into a bounded work session or delivery draft.
5. Treat formal delivery, Office exports, external automation, and release promotion as separately gated outcomes.

## Shared state language

| User-facing state | Intended meaning |
| --- | --- |
| Live/API-backed | The currently displayed record came from a reachable API response. It still may require review or evidence validation. |
| Empty/no real data | No usable record was returned. The web feed does not silently replace this state with demo cards. |
| Local demo/mock | A local fixture or fallback is being shown; the Mini Program presents this as a warning rather than a real sync. |
| Degraded/recovering | A collector, source, retrieval, or session path needs retry, clarification, or operator review. |
| Evidence-gated/HOLD | A template, local test, or preview exists, but required Office, visual, human, external, or release evidence is still absent. |

This map is an orientation guide, not an assertion that every surface has production authorization. For current evidence and release boundaries, read the [public roadmap](./public-roadmap.md) and the versioned product-strategy documents linked there.
