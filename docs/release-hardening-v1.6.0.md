# Release Hardening v1.6.0

Version: `1.6.0+20260613`

## Scope

- Shared Focus/session runtime calculations live in `src/lib/focus-runtime-model.ts` with Vitest coverage.
- Persisted UI preferences are applied before hydration through `src/lib/preference-bootstrap.ts`.
- Legacy slate/white Tailwind utilities remain readable in dark mode while new components use semantic `af-*` tokens.
- `npm run repo:screenshots` builds an isolated production frontend on a free port and captures 15 light plus 4 dark release baselines.
- `research_service.py` no longer contains statically unreferenced private wrappers, and owner tests do not call facade-private functions.

## Release Gates

```bash
npm run check
npm run repo:screenshots
npm run security:scan
npm run security:scan:history
```

The screenshot manifest must report 19 accepted images with both `light` and `dark` themes. History scanning is required before publishing rewritten refs to GitHub and ModelScope.

## Architecture Policy

- Add research behavior to owner modules and inject it through workflow or runtime dependency ports.
- Keep `research_service.py` limited to public compatibility, dependency binding, and workflow entrypoints.
- Split large React components only when a stable state/controller or presentation-section boundary is available.
- Prefer semantic theme classes for new code; the dark compatibility layer is migration support, not the target API.
