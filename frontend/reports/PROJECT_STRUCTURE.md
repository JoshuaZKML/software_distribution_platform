# Frontend Project Structure (Complete Overview)

**Generated:** February 18, 2026  
**Framework:** Next.js 14 (App Router)  
**Language:** TypeScript  
**Build Tool:** Next.js built-in  

---

## Directory Tree

```
frontend/
├── .env.local                           # Environment variables (MSW enabled)
├── .next/                               # Next.js build output (generated)
├── node_modules/                        # Dependencies (generated)
├── public/                              # Static assets served at root
│   └── mockServiceWorker.js             # MSW service worker (v2.12.10)
├── app/                                 # Next.js App Router (pages & layout)
│   ├── layout.tsx                       # Root layout wrapper
│   ├── page.tsx                         # Landing/dashboard (/)
│   ├── globals.css                      # Global styles
│   ├── (auth)/                          # Route group: authentication
│   │   ├── forgot-password/
│   │   │   └── page.tsx
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── register/
│   │   │   └── page.tsx
│   │   ├── reset-password/
│   │   │   └── [token]/
│   │   │       └── page.tsx
│   │   └── verify-email/
│   │       └── [token]/
│   │           └── page.tsx
│   ├── (dashboard)/                    # Route group: protected pages
│   │   ├── layout.tsx                  # Dashboard wrapper (sidebar + topbar)
│   │   ├── dashboard/                  # Empty folder (redundant)
│   │   ├── licenses/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── profile/
│   │   │   └── page.tsx
│   │   └── software/
│   │       └── page.tsx
│   └── products/
│       └── page.tsx
├── components/                          # Reusable React components
│   ├── admin/                           # Admin-specific components
│   ├── layout/                          # Layout primitives
│   │   ├── Providers.tsx                # Root providers (Query, MSW, Auth, Toast)
│   │   ├── Sidebar.tsx                  # Sidebar navigation
│   │   └── TopBar.tsx                   # Top navigation bar
│   ├── product/                         # Product-related components
│   └── ui/                              # UI primitives (shadcn-like patterns)
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx                    # ⚠️ Uses Math.random() for IDs
│       └── Skeleton.tsx
├── lib/                                 # Utility & business logic
│   ├── api/
│   │   ├── client.ts                    # Axios instance + interceptors
│   │   ├── generated.ts                 # Orval auto-generated API client
│   │   └── types.ts                     # Custom types
│   ├── hooks/
│   │   ├── useAuth.ts                   # Zustand auth store
│   │   ├── useDashboardStats.ts         # Dashboard stats query
│   │   ├── useLicenses.ts               # Licenses query
│   │   ├── useToast.ts                  # Toast helper
│   │   └── useWebSocket.ts              # WebSocket connection
│   └── utils/
│       └── cn.ts                        # Class name utility
├── mocks/                               # MSW mock handlers
│   ├── browser.ts                       # setupWorker (browser runtime)
│   ├── server.ts                        # setupServer (Node test runtime)
│   └── handlers/
│       ├── index.ts                     # Handler exports
│       ├── auth.ts                      # Mock /auth/* endpoints
│       ├── dashboard.ts                 # Mock dashboard endpoints
│       └── licenses.ts                  # Mock /licenses/* endpoints
├── types/                               # TypeScript types (if any custom)
├── reports/                             # Documentation (generated)
│   ├── FRONTEND_ASSESSMENT.txt
│   ├── REMEDIATION_CHECKLIST.md
│   ├── DEVELOPER_ONBOARDING.md
│   ├── MSW_REPORT.md
│   └── ERRORS_FOUND.md
│
├── package.json                         # Dependencies & scripts
├── package-lock.json                    # Lock file
├── tsconfig.json                        # TypeScript config (strict: false)
├── tailwind.config.ts                   # Tailwind CSS theme
├── next.config.js                       # Next.js config
├── orval.config.ts                      # Orval code generation config
├── schema.yaml                          # OpenAPI spec (from backend)
├── next-env.d.ts                        # Auto-generated Next types
└── create-app.ps1 / create-app-final.ps1 # Setup scripts (archived)
```

---

## Configuration & Key Files

### Package.json (Scripts)
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "generate-types": "openapi-typescript schema.yaml -o ./types/api.ts",
    "generate-api": "orval"
  },
  "msw": {
    "workerDirectory": ["public"]
  }
}
```

### Environment Variables (.env.local)
```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_USE_REAL_API=false
NEXT_PUBLIC_JWT_STORAGE_KEY=access_token
NEXT_PUBLIC_REFRESH_STORAGE_KEY=refresh_token
```

### Orval Configuration (orval.config.ts)
```typescript
import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: '../schema.yaml',           // Backend OpenAPI spec
    output: {
      target: './src/lib/api/generated/api.ts',
      schemas: './src/lib/api/generated/model',
      client: 'react-query',           // Uses React Query hooks
      mock: true,                      // Generates MSW handlers
      prettier: true,
      override: {
        mutator: {
          path: './src/lib/api/client.ts',
          name: 'apiClient',           // Custom axios wrapper
        },
      },
    },
  },
});
```
**Note:** Orval is configured to generate into `src/lib/api/generated/` but actual code is at `lib/api/`. Path mismatch issue to address.

### TypeScript Config (tsconfig.json)
```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "strict": false,                   // ⚠️ Not strict; consider enabling
    "paths": {
      "@/*": ["./*"]                   // Path alias for imports
    }
  }
}
```

### Tailwind Config (tailwind.config.ts)
- Dark mode: `class`
- Custom colors: border, input, ring, background, primary, secondary, destructive, muted, accent, popover, card
- Font: Inter + custom marketing/app font sizes
- Plugins: @tailwindcss/forms, @tailwindcss/typography

---

## Technology Stack (Exact Versions)

| Category | Package | Version |
|----------|---------|---------|
| **Framework** | next | 14.0.4 |
| **UI Library** | react, react-dom | 18.2.0 |
| **Language** | typescript | (via @types) |
| **State** | zustand | 5.0.11 |
| **Server State** | @tanstack/react-query | 5.90.21 |
| **Forms** | react-hook-form | 7.71.1 |
| **Validation** | zod | 4.3.6 |
| **HTTP** | axios | 1.13.5 |
| **Mocking** | msw | 2.12.10 |
| **Styling** | tailwindcss | 3.4.1 |
| **Icons** | @heroicons/react | 2.2.0 |
| **Notifications** | react-hot-toast | 2.6.0 |
| **Code Gen** | orval, openapi-typescript | 7.13.2, 7.13.0 |
| **Device ID** | @fingerprintjs/fingerprintjs | 5.0.1 |
| **Dev Tools** | @tanstack/react-query-devtools | 5.91.3 |

---

## Data Flow & Architecture

### Authentication Flow
1. User navigates to `/login` (public route).
2. Enters email/password, form submits to `useAuth().login()`.
3. `useAuth` (Zustand) calls `axiosInstance.post('/auth/login/', data)`.
4. MSW intercepts (if enabled) or real backend responds with `{ access, refresh, user }`.
5. Tokens stored in localStorage as `access_token` and `refresh_token`.
6. `useAuth` state updates; router pushes to `/` (dashboard).
7. Dashboard pages access `useAuth().user` from Zustand store.

### API Requests
1. Component uses generated hook (e.g., `useV1LicensesMyLicensesList()` from orval) OR manual `axiosInstance.get(...)`.
2. `axiosInstance` (created in `lib/api/client.ts`) has:
   - Request interceptor: attaches `Authorization: Bearer <access_token>`.
   - Response interceptor: on 401, attempts refresh using `refresh_token`; on success, stores new `access_token` and retries original request.
3. MSW (if enabled) intercepts and returns mocked data; otherwise, backend API responds.

### State Management
- **Auth**: Zustand `useAuth` store (single source of truth for user, tokens, auth status).
- **Server State**: React Query with devtools for data fetching caching.
- **UI State**: React useState within components (no global UI state store).

---

## Backend API Contract (Observed)

### Base URL
`NEXT_PUBLIC_API_URL` = `http://localhost:8000/api/v1`

### Key Endpoints
| Method | Endpoint | Response |
|--------|----------|----------|
| POST | /auth/login/ | `{ access, refresh, user }` |
| POST | /auth/token/refresh/ | `{ access }` |
| GET | /auth/users/me/ | `{ id, email, first_name, role, ... }` |
| GET | /licenses/my-licenses/ | `{ summary, licenses_by_software }` |
| GET | /licenses/activation-codes/:id/ | License object |

(More endpoints in `schema.yaml` and mocks.)

---

## Development Workflow

### Step 1: Start Dev Server
```bash
cd frontend
npm run dev
```

### Step 2: Verify MSW
- Open `http://localhost:3000`.
- Open browser DevTools console.
- Should see: `[MSW] Service Worker started successfully`.

### Step 3: Test Login (with MSW)
- Click login link.
- Enter: `admin@example.com` / `password`.
- Should redirect to dashboard and show stats (mocked data).

### Step 4: Generate API Types (if backend schema changes)
```bash
npm run generate-api     # Runs orval (needs orval.config.ts path fix)
npm run generate-types   # Runs openapi-typescript
```

---

## Known Issues & Mitigations

| Issue | File | Severity | Status |
|-------|------|----------|--------|
| Hydration ID mismatch | `components/ui/Input.tsx` | 🔴 High | Unfixed (use React.useId()) |
| MSW behind redirect | Middleware + orval config | 🔴 High | Partially fixed |
| ESM bundling warning | `lib/api/*` | 🟡 Medium | Investigate server imports |
| Orval path mismatch | `orval.config.ts` | 🟡 Medium | Points to `src/lib/api/generated` |
| Token naming consistency | `useAuth.ts` + `client.ts` | 🟡 Medium | Fixed but needs constants file |
| No TypeScript strict mode | `tsconfig.json` | 🟡 Medium | Enable for safety |

---

## Development Ergonomics & Quick References

### Import Path Alias
Use `@/` for absolute imports (configured in tsconfig):
```typescript
import { useAuth } from '@/lib/hooks/useAuth';
import { Button } from '@/components/ui/Button';
```

### Adding a New Page
1. Create file: `app/(route-group)/page-name/page.tsx`.
2. Export default React component.
3. Use `'use client'` at top if client-side features needed.

### Adding a New Component
1. Create file: `components/category/ComponentName.tsx`.
2. Export as named export (or default).
3. Use in pages/other components via `@/components/...` import.

### Debugging MSW Handlers
- Add console logs inside handler functions in `mocks/handlers/*.ts`.
- Check Network tab for CSP violations or "mocked" badge (indicates MSW intercepted).

---

## Next Steps (As of Feb 18, 2026)

1. Fix orval config path: change `./src/lib/api/generated/` to `./lib/api/generated/`.
2. Fix Input.tsx hydration: replace `Math.random()` with `React.useId()`.
3. Add `lib/constants/auth.ts` for token key centralization.
4. Enable TypeScript strict mode and fix errors.
5. Add unit & E2E tests; set up CI/CD.

---

**End of Project Structure Overview**
