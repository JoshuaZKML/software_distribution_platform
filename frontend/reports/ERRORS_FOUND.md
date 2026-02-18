Errors Found (read-only assessment)
===================================

1) Hydration mismatch in forms
   - File: `components/ui/Input.tsx`
   - Symptom: React warnings like "Prop `htmlFor` did not match. Server: ... Client: ..." during hydration.
   - Root cause: `Math.random()` used to generate id on server and client differently.
   - Fix: Use `React.useId()` or `useState(() => ...)` to create a stable id per instance.

2) MSW Service Worker registration error (redirect)
   - Symptom: "Failed to register a ServiceWorker: The script resource is behind a redirect"
   - Root cause: middleware/rewrite intercepting `/mockServiceWorker.js`, or public assets not served directly.
   - Fix: allow `/mockServiceWorker.js` in middleware publicPaths; remove conflicting rewrites.

3) Token key mismatch and SSR cookie mismatch
   - Symptom: Authentication failing intermittently or middleware redirecting to login.
   - Root cause: earlier code used `accessToken`/`refreshToken` vs current `access_token`/`refresh_token`. Server middleware sometimes checks cookie name `accessToken`.
   - Fix: centralize token key names in a constant and ensure both client and server agree; prefer httpOnly cookie approach for SSR-authenticated pages.

4) ESM bundling warnings
   - Symptom: Dev logs show "ESM packages (supports-color) need to be imported" from `debug/src/node.js` via `follow-redirects` -> `axios` server adapters.
   - Root cause: server-only modules leaking into client bundle or mixed ESM/CJS packages causing bundler issues.
   - Fix: audit imports and keep server-only code in server-only files. Configure `next.config.js` `transpilePackages` or alias problematic packages to browser builds.

5) Missing/empty dashboard sub-page folder
   - Symptom: `app/(dashboard)/dashboard/` folder empty while `app/page.tsx` holds dashboard.
   - Impact: developer confusion and possible route collisions.
   - Fix: Consolidate dashboard pages into a clear route structure and remove empty folders or add README.

6) Lack of automated tests / CI
   - Symptom: Frequent regressions and manual fixes required.
   - Fix: Add unit and E2E tests and CI pipeline.

Notes
-----
All issues documented above are fixable without backend changes and were prioritized in `REMEDIATION_CHECKLIST.md`.
