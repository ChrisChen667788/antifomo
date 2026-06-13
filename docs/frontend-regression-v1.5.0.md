# Frontend Regression Baseline v1.5.0

## Scope

The first frontend unit/component baseline protects behavior that was previously embedded inside large client components:

- inbox research keyword grouping, research-mode budgets, source-tier classification, progress-stage mapping, and delivery supplement defaults
- markdown archive parsing, section canonicalization, item deduplication, archive comparison, and encoded archive navigation
- application preference loading, system-theme resolution, and synchronization of theme/font/text-size/language attributes to the root HTML element

The extraction does not change route contracts, rendered markup, CSS classes, or the semantic theme-token system.

## Commands

```bash
npm run test:frontend
npm run test:frontend:watch
npm run check
```

`npm run check` now runs lint, frontend tests, a production Next.js build, and the backend test suite in that order.

## Ownership

- `src/components/inbox/inbox-form-model.ts` owns non-React inbox research behavior.
- `src/components/research/research-markdown-archive-model.ts` owns non-React archive behavior.
- `src/components/settings/app-preferences-provider.test.tsx` protects theme preference integration with the DOM.

## Remaining UI Work

- add screenshot comparisons for explicit light and dark routes
- split presentation-only sections from `inbox-form.tsx` and `research-markdown-archive-viewer.tsx` when their UI changes
- add focused tests for session summary, focus timer, and research compare models before further decomposition

## Dependency Security Note

Next.js and `eslint-config-next` are upgraded from `16.1.6` to `16.2.9`. `npm audit` still reports the PostCSS version pinned inside the official Next.js package. The automated force fix proposes an unsafe downgrade to Next 9, so it is intentionally not applied; this residual build-time warning should be rechecked on the next Next.js patch.
