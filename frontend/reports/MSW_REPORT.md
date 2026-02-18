MSW (Mock Service Worker) Report
================================

Current setup (read-only)
-------------------------
- Worker file: `public/mockServiceWorker.js` (present)
- Browser setup: `mocks/browser.ts` → `export const worker = setupWorker(...handlers)`
- Server setup for tests: `mocks/server.ts` → `setupServer(...handlers)`
- Handlers: `mocks/handlers/*` (auth, licenses, dashboard) use `msw/http` helper patterns and faker for realistic data.
- package.json: `msw.workerDirectory = ["public"]` ensures worker file placement for Next dev.

Observed issues and mitigations
-------------------------------
1. Service worker behind redirect
   - Root cause: middleware or Next rewrites intercepting `/mockServiceWorker.js` and redirecting it. This makes `navigator.serviceWorker.register('/mockServiceWorker.js')` fail with "script behind redirect".
   - Fix: allow `/mockServiceWorker.js` in app middleware public path whitelist (or remove conflicting rewrite).

2. Silent failures in Providers
   - Providers previously swallowed errors. Current `Providers.tsx` logs and attempts worker.start() only in development with NEXT_PUBLIC_USE_REAL_API !== 'true'. Ensure logs show registration success.

3. Unhandled requests
   - Handler config uses `onUnhandledRequest: 'warn'` to help surface missing mocks; keep this setting during development.

Recommendations
---------------
- Keep `public/mockServiceWorker.js` committed and avoid server redirects.
- Add a small healthcheck page `/__msw_status` (dev-only) that confirms worker state by posting a message to the SW and awaiting a response.
- Add MSW integration test: start Node server (mocks/server) and run a couple of axios requests to validate mocked responses.

Developer instructions for MSW debugging
---------------------------------------
1. Start dev with `NEXT_PUBLIC_USE_REAL_API=false`.
2. Open browser console and look for: `[MSW] Service Worker started successfully` and any `onUnhandledRequest` warnings.
3. If SW fails with redirect, run `curl -I http://localhost:3000/mockServiceWorker.js` and confirm 200 response (no redirect).
