Developer Onboarding (Frontend)
===============================

Quick start
-----------
1. Clone the repository and open `frontend/`.
2. Copy `.env.local.example` to `.env.local` (or edit `.env.local`) and set:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_USE_REAL_API=false
```

3. Install and run:

```bash
npm ci
npm run dev
```

4. Open `http://localhost:3000`.

Dev notes
---------
- MSW (Mock Service Worker) runs in dev when `NEXT_PUBLIC_USE_REAL_API` is `false`. Confirm browser console shows MSW logs.
- Login with mocked credentials: `admin@example.com` / `password`.

Key files to read first
----------------------
- `app/layout.tsx` (root layout)
- `components/layout/Providers.tsx` (MSW + Query + Auth init)
- `lib/hooks/useAuth.ts` (auth store)
- `lib/api/client.ts` (axios instance + interceptors)
- `mocks/handlers/*` (mock API responses)

Where to make safe changes
-------------------------
- UI components: `components/ui/*` — aim for small, well-tested units.
- API client: use `lib/api/client.ts` and `apiClient` wrapper for generated code.

How to run tests (recommended additions)
---------------------------------------
- Add Jest + React Testing Library for unit tests.
- Add Playwright for E2E tests; run Playwright against dev server with MSW enabled.

Contact points
--------------
- For API contract questions, inspect `schema.yaml` and `lib/api/generated.ts`.
- For MSW issues, check `public/mockServiceWorker.js` and `mocks/browser.ts`.
