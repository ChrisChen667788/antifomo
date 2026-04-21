# WorkBuddy Official Cutover

## Current State

- Official Tencent `CodeBuddy` CLI is installed locally.
- Current API health exposes:
  - `official_cli_detected`
  - `official_cli_authenticated`
  - `official_gateway_configured`
  - `official_gateway_reachable`
- Before login, the system stays on the local compatibility adapter.

## What Is Already Wired

- `GET /api/workbuddy/health`
  - Detects official CLI install/auth state.
  - Detects configured official gateway state.
- `Focus Assistant -> WorkBuddy`
  - If official CLI is authenticated, the bridge can call official CLI.
  - If not, it falls back to the local adapter and records bridge metadata.

## Required User Step

Run:

```bash
codebuddy
```

Then enter:

```text
/login
```

Complete browser login.

## How To Verify

### 1. CLI self-check

```bash
bash scripts/workbuddy_official_doctor.sh
```

Expected after login:

- `official_cli_detected = true`
- `official_cli_authenticated = true`

### 2. Web UI

Open:

- `http://127.0.0.1:3000/settings`

Check the `WorkBuddy` panel:

- Official CLI should show `authenticated`
- Gateway may still be `not configured`, which is acceptable if CLI bridge is the active official path

### 3. Focus Assistant

Open:

- `http://127.0.0.1:3000/focus`

Trigger a `WorkBuddy` action.

If official CLI is active, task output should include a `workbuddy_bridge` block with:

- `provider = tencent_codebuddy_cli`
- `official_cli_used = true`

If not logged in, it will show:

- `provider = local_adapter`
- `official_cli_used = false`

## Remaining Optional Step

If later you want the official gateway path in addition to CLI bridge, configure:

- `WORKBUDDY_OFFICIAL_GATEWAY_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_HEALTH_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_WEBHOOK_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_BEARER_TOKEN`

## Notes

- This project does not use Tencent official SDK packages directly inside Python/Next runtime.
- The current official path is via installed Tencent `CodeBuddy` CLI plus health/auth probing and execution bridge.
