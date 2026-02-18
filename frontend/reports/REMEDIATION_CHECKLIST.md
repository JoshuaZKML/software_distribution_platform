Remediation Checklist (prioritized)
===================================

High priority (apply ASAP, minimal disruption)
----------------------------------------------
- Fix hydration IDs in `components/ui/Input.tsx`.
  - Use `React.useId()` or `useState` to create stable ids.
- Ensure MSW service worker is served without redirects.
  - Confirm middleware / rewrites allow `/mockServiceWorker.js` and public assets.
- Token naming consistency: centralize token key names.
  - Add `lib/constants/auth.ts` with `ACCESS_TOKEN_KEY` and `REFRESH_TOKEN_KEY`.
  - Update `useAuth` and `lib/api/client.ts` to import these constants.

Medium priority
---------------
- Audit imports for server-only modules being bundled client-side (e.g., debug/supports-color). Move server-only code behind server-only entrypoints.
- Confirm Orval generated client uses `apiClient` browser mutator; add tests for generated API compatibility.
- Add small unit tests for `useAuth` and `Providers` initialization (MSW mocking integration test using msw/node).

Longer-term (hardening)
----------------------
- Enable TypeScript `strict` mode; fix resulting issues.
- Add CI pipeline (GitHub Actions) to run `npm run build`, typecheck, and tests on PRs.
- Add E2E (Playwright) tests for login → dashboard flow with MSW.
- Add Sentry frontend integration and ensure axios interceptor reports context.

Developer ergonomics
--------------------
- Document: `README.dev.md` with quick start and MSW configuration.
- Add `lib/constants/env.ts` validator that runs on startup and warns if envs conflict (NEXT_PUBLIC_USE_REAL_API vs NEXT_PUBLIC_API_URL).

Rollback notes
--------------
- All changes above are additive and non-breaking. If anything goes wrong, revert specific commits. Preserve backward compatibility by keeping API contracts intact.
