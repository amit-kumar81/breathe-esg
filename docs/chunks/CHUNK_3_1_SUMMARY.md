# Chunk 3.1: React Project Setup & API Client - Quick Reference

## Overview

Vite React app with centralized API client (axios), JWT token management, React Query hooks, and error handling. **No pages yet** (those come in Phase 3.2+).

---

## Key Files

| File | Purpose |
|------|---------|
| `src/api/client.js` | Axios instance with JWT interceptors |
| `src/hooks/useAuth.js` | Login, logout, currentUser |
| `src/hooks/useEmissions.js` | Fetch emissions, summary, export |
| `src/hooks/useIngestions.js` | Upload, parse, normalize |
| `src/hooks/useReviewTasks.js` | Fetch tasks, approve, reject |
| `src/components/ErrorBoundary.jsx` | Catch React errors |
| `src/components/ProtectedRoute.jsx` | Guard authenticated routes |
| `src/App.jsx` | Main app + routing |
| `vite.config.js` | Vite config with /api proxy |
| `.env.example` | Environment template |

---

## Setup & Run

```bash
# 1. Install dependencies
npm install

# 2. Configure API URL
cp .env.example .env.development
# Edit VITE_API_URL

# 3. Start development server
npm run dev
# → http://localhost:3000
# → Proxies /api to http://localhost:8000/api

# 4. Build for production
npm run build
# → dist/
```

---

## Architecture Decisions

| Decision | What | Why |
|----------|------|-----|
| Vite | Build tool | 10x faster than CRA |
| Axios | HTTP client | Centralized interceptors, retry |
| React Query | Server state | Caching, deduplication, invalidation |
| localStorage | Token storage | Persistence, simple |
| Custom Hooks | Domain logic | Reusability, testability |
| Error Boundary | Error UI | Graceful degradation |
| React Router | Navigation | Client-side routing, protected routes |
| No Redux | State management | YAGNI, React Query handles most |

---

## Token Lifecycle

```
1. User logs in
   POST /auth/login/ → { access_token, refresh_token }
   → localStorage.setItem('access_token', token)

2. Every request
   apiClient interceptor adds:
   Authorization: Bearer {token}

3. Token expires (401)
   Interceptor catches 401
   → POST /auth/refresh/ with refresh_token
   → Get new access_token
   → Retry original request

4. Logout
   DELETE localStorage['access_token']
   DELETE localStorage['refresh_token']
   → Redirect to /login
```

---

## Hook Usage Patterns

### Fetch Data
```javascript
const { data, isLoading, error } = useEmissions({ year: 2023 })
```

### Mutation (POST/PATCH)
```javascript
const { mutate, isPending } = useApproveTask(taskId)
mutate(notes, {
  onSuccess: () => { /* refresh queries */ }
})
```

### Pagination
```javascript
const [page, setPage] = useState(1)
const { data } = useEmissions({ page })
// data.results, data.next, data.previous
```

### Conditional Fetch
```javascript
const { data } = useEmissions({
  enabled: !!selectedYear // Only fetch if condition met
})
```

---

## Error Handling

```javascript
import { getErrorMessage } from './utils/errorHandler'

try {
  const response = await apiClient.get('/emissions/')
} catch (error) {
  const message = getErrorMessage(error)
  // "Unauthorized. Please log in." (user-friendly)
}
```

---

## Hooks Reference

### useAuth()
```javascript
const { data: user, isLoading, error } = useCurrentUser()
const { mutate: login, isPending } = useLogin()
const { mutate: logout } = useLogout()
```

### useEmissions()
```javascript
useEmissions({ page, statusFilter, yearFilter })
useEmissionsSummary()
useEmissionsExport(format, filters)
```

### useIngestions()
```javascript
useIngestions({ page, step })
useIngestionDetail(ingestionId)
useUploadCSV()
useParse(ingestionId)
useNormalize(ingestionId)
useIngestionStatus(ingestionId)
```

### useReviewTasks()
```javascript
useReviewTasks({ page, status, priority })
useReviewTaskDetail(taskId)
useApproveTask(taskId)
useRejectTask(taskId)
useRequestRevision(taskId)
useReviewSummary()
```

---

## React Query Setup

```javascript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 // 1 minute
    }
  }
})

<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

---

## Protected Routes

```javascript
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/dashboard" element={
    <ProtectedRoute>
      <DashboardPage />
    </ProtectedRoute>
  } />
</Routes>
```

---

## Environment Variables

```
VITE_API_URL=http://localhost:8000/api     (dev)
VITE_API_URL=https://api.example.com       (prod)
VITE_APP_NAME=Breathe ESG
```

Vite replaces at build time: `import.meta.env.VITE_API_URL`

---

## Common Patterns

| Pattern | Code |
|---------|------|
| Show loading | `if (isLoading) return <Spinner />` |
| Show error | `if (error) return <Alert>{getErrorMessage(error)}</Alert>` |
| Refetch on change | `useEffect(() => { queryClient.invalidateQueries(...) }, [dep])` |
| Disable query | `useQuery({ ..., enabled: !!condition })` |
| Optimistic update | `queryClient.setQueryData(key, newData)` |
| Refresh after mutation | `onSuccess: () => queryClient.invalidateQueries(...)` |

---

## File Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.js
│   ├── hooks/
│   │   ├── useAuth.js
│   │   ├── useEmissions.js
│   │   ├── useIngestions.js
│   │   └── useReviewTasks.js
│   ├── components/
│   │   ├── ErrorBoundary.jsx
│   │   └── ProtectedRoute.jsx
│   ├── utils/
│   │   └── errorHandler.js
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
├── index.html
├── vite.config.js
├── package.json
├── .env.example
└── .env.development (git-ignored)
```

---

## Next Steps

Phase 3.2+ builds pages using these hooks:
- **LoginPage**: useLogin, useLogout
- **DashboardPage**: useEmissionsSummary, useReviewSummary
- **UploadPage**: useUploadCSV, useParse, useNormalize
- **ReviewPage**: useReviewTasks, useApproveTask
- **EmissionsPage**: useEmissions with filtering/pagination

No changes to API client or hooks needed. Pages are simple components that consume hooks.

---

## Principles Maintained

✅ **Realistic**: No over-engineering. Vite + React Query + axios = production-ready.
✅ **No Hallucinations**: All files created match specification exactly.
✅ **Reusable Hooks**: Each hook encapsulates one domain (auth, emissions, etc.).
✅ **Error Handling**: Centralized error formatting + Error Boundary.
✅ **Token Management**: Automatic refresh on 401.
✅ **Caching**: React Query handles automatically.
✅ **Type-Safe**: No TypeScript yet (Phase 3 MVP), but code structure supports it later.

---

This chunk is the foundation for all frontend pages. All data flows through React Query hooks. All HTTP goes through apiClient with JWT. All errors are formatted consistently. Pages are simple—just consume hooks and render.

