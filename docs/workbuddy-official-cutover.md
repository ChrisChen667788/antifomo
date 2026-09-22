# WorkBuddy Compatibility and CodeBuddy CLI Bridge

This document describes a local compatibility/CLI bridge. The historical filename is retained for links. It is not evidence that Anti-FOMO is an official Tencent-hosted WorkBuddy Enterprise tenant. See the [WorkBuddy comparison](./workbuddy-deep-dive-2026-09-18.md), [engineering plan](./workbuddy-integration-plan-2026-09-18.md), and [current product status](./current-product-status.md).

## Current State

- The adapter can detect an installed Tencent `CodeBuddy` CLI. Installation and authentication are machine-specific; check health on the machine you use.
- Current API health exposes:
  - `official_cli_detected`
  - `official_cli_authenticated`
  - `official_gateway_configured`
  - `official_gateway_reachable`
- Health reports CLI authentication and gateway reachability separately. A reachable configured gateway takes precedence in the health label, regardless of CLI login. This probe is not an end-to-end task test.
- The existing webhook verifies signatures only when `WORKBUDDY_WEBHOOK_SECRET` is nonempty; otherwise it reports `signature_bypassed_no_secret`. Supported export tasks execute directly, and results can be sent to request-supplied or configured callback URLs. This path has no universal human-approval or scoped-callback gate today. Version 2.12.0 plans the migration before broader execution is enabled.

## What Is Already Wired

- `GET /api/workbuddy/health`
  - Detects official CLI install/auth state.
  - Detects configured official gateway state.
- `Focus Assistant -> WorkBuddy`
  - `WORKBUDDY_MODE=local` skips CLI delegation, even if it is installed and authenticated.
  - In other modes, Focus can call CodeBuddy CLI to summarize the generated result. A successful call records `official_cli_used=true`; an unsuccessful call records local-adapter metadata. Login alone does not guarantee success.

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

- `http://127.0.0.1:3010/settings`

Check the `WorkBuddy` panel:

- Official CLI should show `authenticated`
- Gateway may still be `not configured` when the CodeBuddy CLI bridge is active. A configured gateway URL and successful health probe alone do not establish WorkBuddy-native interoperability.

### 3. Focus Assistant

Open:

- `http://127.0.0.1:3010/focus`

Trigger a `WorkBuddy` action.

When mode allows CLI delegation and the call succeeds, task output includes a `workbuddy_bridge` block with:

- `provider = tencent_codebuddy_cli`
- `official_cli_used = true`

When a CLI call is attempted but unsuccessful (including missing login), the bridge block shows:

- `provider = local_adapter`
- `official_cli_used = false`

In `local` mode the CLI path is skipped and this bridge block may be absent. The Focus implementation currently invokes the CLI; gateway health alone does not route this action through a gateway.

## Remaining Optional Step

If later you want the official gateway path in addition to CLI bridge, configure:

- `WORKBUDDY_OFFICIAL_GATEWAY_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_HEALTH_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_WEBHOOK_URL`
- `WORKBUDDY_OFFICIAL_GATEWAY_BEARER_TOKEN`

## Notes

- This project does not use Tencent official SDK packages directly inside Python/Next runtime.
- The current official path is via installed Tencent `CodeBuddy` CLI plus health/auth probing and execution bridge.
