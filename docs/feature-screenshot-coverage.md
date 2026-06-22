# Feature Screenshot Coverage

Version: `1.7.2+20260615`

This gallery is the release checklist for GitHub-facing product screenshots. Each primary product surface must have at least one current, content-bearing screenshot before a release is pushed.

The current baseline contains 30 screenshots: 15 primary surfaces in light
mode and the same 15 surfaces in dark mode. It was regenerated on
`2026-06-21` after the P2.2 formal-delivery export update, so nested progress,
knowledge, collector, settings, Focus, research, and Inbox delivery surfaces are
covered instead of only the original four dark-mode routes.

With the backend running on port `8000`, refresh and validate the full set through an isolated production frontend:

```bash
npm run repo:screenshots
```

The release harness builds the application, allocates a free localhost port, starts `next start`, captures the matrix, and stops only that isolated frontend process. `npm run repo:screenshots:capture` remains available when a compatible frontend is already running.

The capture script also writes `docs/assets/screenshots/screenshot-manifest.json` and rejects screenshots that are too small, captured with a runtime error overlay, or rendered with a theme different from the declared manifest entry. All 15 primary release surfaces have both light and dark baselines.

## Coverage Matrix

| Surface | Screenshot | Release note |
| --- | --- | --- |
| Home signal dashboard | `docs/assets/screenshots/home-signal-dashboard.png` | First-screen signal triage, WeChat Favorites import entry, and route switching. |
| Inbox / research workspace | `docs/assets/screenshots/inbox-research-workspace.png` | Intake, report generation, scenario refinement, architecture readiness, architect workbench review, and formal export. |
| Saved / read-later workspace | `docs/assets/screenshots/saved-readlater-workspace.png` | Saved-item review with topic and score context. |
| Focus session workspace | `docs/assets/screenshots/focus-session-workspace.png` | Bounded focus session with headless-source-first collection startup and WeChat PC supplementary URL harvesting. |
| Session summary workspace | `docs/assets/screenshots/session-summary-workspace.png` | Session metrics, markdown summary, reading list, and follow-up drafts. |
| Collector operations workspace | `docs/assets/screenshots/collector-operations-workspace.png` | Desktop collector, source health diagnostics, coverage/body-success rates, OCR backfill, pending queue, and daily export operations. |
| Settings and tuning workspace | `docs/assets/screenshots/settings-tuning-workspace.png` | Preferences, WorkBuddy, collector, and recommender controls. |
| Knowledge library workspace | `docs/assets/screenshots/knowledge-library-workspace.png` | Knowledge list, commercial dashboard, saved intelligence, and review signals. |
| Knowledge commercial hub | `docs/assets/screenshots/knowledge-commercial-hub.png` | Account intelligence, opportunities, review queue, and follow-up actions. |
| Knowledge merge workflow | `docs/assets/screenshots/knowledge-merge-workflow.png` | Merge preview, inherited state checks, and target-title workflow. |
| Research center dashboard | `docs/assets/screenshots/research-center-dashboard.png` | Watchlists, archive entry points, retrieval health, solution architecture readiness, and delivery diagnostics. |
| Research topic workspace | `docs/assets/screenshots/research-topic-workspace.png` | Topic versions, evidence density, follow-up impact, and change tracking. |
| Research compare workspace | `docs/assets/screenshots/research-compare-workspace.png` | Version comparison, account signals, competitor deltas, and export context. |
| Research experiment orchestration | `docs/assets/screenshots/research-experiment-control-plane.png` | Cohorts, baselines, rollout gates, manifests, and runtime policy diagnostics. |
| Research archive viewer | `docs/assets/screenshots/research-archive-viewer.png` | Historical markdown archive, delivery digest, section links, and version context. |
| Home signal dashboard, dark | `docs/assets/screenshots/home-signal-dashboard-dark.png` | Explicit dark-theme feed and navigation regression baseline. |
| Inbox / research workspace, dark | `docs/assets/screenshots/inbox-research-workspace-dark.png` | Explicit dark-theme intake and research regression baseline. |
| Saved / read-later workspace, dark | `docs/assets/screenshots/saved-readlater-workspace-dark.png` | Explicit dark-theme saved-item regression baseline. |
| Focus session workspace, dark | `docs/assets/screenshots/focus-session-workspace-dark.png` | Explicit dark-theme Focus regression baseline. |
| Session summary workspace, dark | `docs/assets/screenshots/session-summary-workspace-dark.png` | Explicit dark-theme summary regression baseline. |
| Collector operations workspace, dark | `docs/assets/screenshots/collector-operations-workspace-dark.png` | Explicit dark-theme collector regression baseline. |
| Knowledge library workspace, dark | `docs/assets/screenshots/knowledge-library-workspace-dark.png` | Explicit dark-theme knowledge regression baseline. |
| Knowledge commercial hub, dark | `docs/assets/screenshots/knowledge-commercial-hub-dark.png` | Explicit dark-theme commercial intelligence regression baseline. |
| Knowledge merge workflow, dark | `docs/assets/screenshots/knowledge-merge-workflow-dark.png` | Explicit dark-theme merge workflow regression baseline. |
| Research center dashboard, dark | `docs/assets/screenshots/research-center-dashboard-dark.png` | Explicit dark-theme research operations regression baseline. |
| Research topic workspace, dark | `docs/assets/screenshots/research-topic-workspace-dark.png` | Explicit dark-theme topic workspace regression baseline. |
| Research compare workspace, dark | `docs/assets/screenshots/research-compare-workspace-dark.png` | Explicit dark-theme comparison regression baseline. |
| Research experiment orchestration, dark | `docs/assets/screenshots/research-experiment-control-plane-dark.png` | Explicit dark-theme experiment-control regression baseline. |
| Research archive viewer, dark | `docs/assets/screenshots/research-archive-viewer-dark.png` | Explicit dark-theme archive regression baseline. |
| Settings and tuning workspace, dark | `docs/assets/screenshots/settings-tuning-workspace-dark.png` | Explicit dark-theme preference and operations regression baseline. |

## Gallery

<table>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/home-signal-dashboard.png" alt="Home signal dashboard screenshot" />
      <p><strong>Home signal dashboard</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/inbox-research-workspace.png" alt="Inbox research workspace screenshot" />
      <p><strong>Inbox / research workspace</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/saved-readlater-workspace.png" alt="Saved read-later workspace screenshot" />
      <p><strong>Saved / read-later workspace</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/focus-session-workspace.png" alt="Focus session workspace screenshot" />
      <p><strong>Focus session workspace</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/session-summary-workspace.png" alt="Session summary workspace screenshot" />
      <p><strong>Session summary workspace</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/collector-operations-workspace.png" alt="Collector operations workspace screenshot" />
      <p><strong>Collector operations workspace</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/settings-tuning-workspace.png" alt="Settings and tuning workspace screenshot" />
      <p><strong>Settings and tuning workspace</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/knowledge-library-workspace.png" alt="Knowledge library workspace screenshot" />
      <p><strong>Knowledge library workspace</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/knowledge-commercial-hub.png" alt="Knowledge commercial hub screenshot" />
      <p><strong>Knowledge commercial hub</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/knowledge-merge-workflow.png" alt="Knowledge merge workflow screenshot" />
      <p><strong>Knowledge merge workflow</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/research-center-dashboard.png" alt="Research center dashboard screenshot" />
      <p><strong>Research center dashboard</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/research-topic-workspace.png" alt="Research topic workspace screenshot" />
      <p><strong>Research topic workspace</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/research-compare-workspace.png" alt="Research compare workspace screenshot" />
      <p><strong>Research compare workspace</strong></p>
    </td>
    <td width="50%">
      <img src="./assets/screenshots/research-experiment-control-plane.png" alt="Research experiment orchestration screenshot" />
      <p><strong>Research experiment orchestration</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./assets/screenshots/research-archive-viewer.png" alt="Research archive viewer screenshot" />
      <p><strong>Research archive viewer</strong></p>
    </td>
    <td width="50%"></td>
  </tr>
</table>

## Screenshot Acceptance Rules

- Every primary navigation surface must have a current screenshot.
- Every listed primary surface must have both a light and dark screenshot.
- Every screenshot must be captured from the local product, not a mockup.
- Screenshots with runtime overlays, blank panels, obviously empty critical content, or weak demo content should be discarded and recaptured after improving the demo state.
- Release screenshots should favor surfaces that show evidence, diagnostics, deliverables, or operating controls rather than empty setup states.
- The manifest must match the version being released.
