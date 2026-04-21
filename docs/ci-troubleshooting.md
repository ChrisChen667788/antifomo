# CI Troubleshooting

## Jobs

- `check`: runs `npm run check`
- `smoke`: starts an isolated backend on `127.0.0.1:8000` and runs `npm run demo:smoke`
- `focus-e2e`: starts `next start`, launches Chrome, and runs `npm run demo:focus-e2e`

## Artifacts

- `next-build`
  - uploaded by `check`
  - consumed by `focus-e2e`
- `smoke-artifacts`
  - `smoke-report.json`
  - `health.json`
  - `create-item-request.json`
  - `create-item.json`
  - `items.json`
  - `backend.log`
- `focus-e2e-artifacts`
  - `focus-e2e-report.json`
  - `frontend.log`
  - `isolated-backend.log`
  - `focus-ready.*`
  - `focus-paused.*`
  - `focus-resumed.*`
  - `focus-failure-summary.*`
  - `focus-failure-detail.*`

## Local Replay

### `check`

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run check
```

### `smoke`

Start backend first, then run:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
SMOKE_ARTIFACT_DIR=.tmp/smoke-artifacts SMOKE_REPORT_FILE=.tmp/smoke-report.json npm run demo:smoke
```

### `focus-e2e`

Make sure frontend is reachable on `http://127.0.0.1:3000`, then run:

```bash
cd /Users/chenhaorui/PyCharmMiscProject/.idea/anti-fomo-demo
npm run demo:focus-e2e -- --report-file .tmp/focus-e2e-report.json --artifact-dir .tmp/focus-e2e-artifacts
```

## Fast Diagnosis

### `check` fails

- Run `npm run check` locally first.
- If failure is in backend tests, inspect `backend/tests` diff before touching workflow.
- If failure is in build only, compare local `.env` usage with CI defaults.

### `smoke` fails

- Open `smoke-report.json` first. It tells you which stage failed: `health_check`, `create_item`, or `list_items`.
- If `health_check` fails, inspect `backend.log`.
- If `create_item` or `list_items` fails, compare `create-item.json` and `items.json`.

### `focus-e2e` fails

- Open `focus-e2e-report.json` first.
- If `currentStage` points to `open_frontend` or `open_focus`, inspect `frontend.log`.
- If assertions fail, check `focus-paused.snapshot.json`, `focus-resumed.snapshot.json`, and browser `consoleMessages`.
- If the page is broken early, use `focus-failure-summary.png` for the first screen and `focus-failure-detail.png` for the full page.
