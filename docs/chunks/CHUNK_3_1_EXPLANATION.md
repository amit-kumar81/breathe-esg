# Chunk 3.1: React Project Setup & API Client - Detailed Explanation

## Overview

Chunk 3.1 establishes the foundation for the frontend: a Vite-based React app with centralized API client, JWT token management, custom data-fetching hooks, and error handling. No page components yet (those come in 3.2+), just the infrastructure.

---

## Architecture Decision 1: Vite vs. Create React App

### The Decision
Use **Vite** with `@vitejs/plugin-react` for the React project setup.

```bash
# Not CRA:
npx create-react-app frontend

# Yes Vite:
npm create vite@latest frontend -- --template react
```

### Why This Decision

**Build Speed**: Vite is 10-20x faster than Webpack (CRA). Development startup: <100ms vs. 2-5s for CRA.

**ES Modules Native**: Vite uses native ESM, not bundling everything upfront. Hot Module Replacement (HMR) is instant.

**Simpler Config**: Vite config is 10 lines. CRA hides webpack behind ejection.

**Modern Tooling**: Vite is modern, actively maintained. CRA is becoming legacy (React team doesn't promote it).

### When to Switch Back
If you need:
- CRA's built-in testing setup (Jest) → Install vitest + @testing-library/react separately (2 lines)
- CRA's out-of-box build → Vite build is equally simple
- SSR (server-side rendering) → Use Vite with adapters (Remix, SvelteKit model)

### Alternative Considered: Next.js
```javascript
// Next.js app router
export default function Page() { ... }
// Automatic routing, server components, etc.
```

**Why Not**: Overkill for Phase 3.1. No server-side rendering needed yet. Next.js adds complexity (file-based routing, API routes). Stick with plain React + Vite until SSR is required.

---

## Architecture Decision 2: Axios + Manual Interceptors vs. Fetch API

### The Decision
Use **axios** with request/response interceptors for JWT token management.

```javascript
// ✅ Axios with interceptors:
const apiClient = axios.create({ baseURL: API_URL })
apiClient.interceptors.request.use(config => {
  config.headers.Authorization = `Bearer ${token}`
  return config
})

// ❌ NOT bare fetch:
const token = localStorage.getItem('token')
fetch('/api/endpoint', {
  headers: { 'Authorization': `Bearer ${token}` }
})
// Token management is manual on every call
```

### Why This Decision

**Centralized Token Management**: One place (interceptor) to attach/refresh tokens. Fetch requires manual wrapping on every call.

**Automatic Retries**: Interceptor can retry on 401 (token expiry) without request duplication.

**Error Handling**: Single place to handle API errors (format, logging, redirect on 401).

**DRY (Don't Repeat Yourself)**: Fetch requires repeating headers on every call. Axios does it once.

### Refresh Token Flow
```javascript
// 401 Unauthorized → Try refreshing token
if (error.response?.status === 401) {
  const newToken = await refresh()
  // Retry original request with new token
  return apiClient(originalRequest)
}
```

Fetch would require wrapper function on every endpoint.

### Alternative Considered: TanStack Query Mutator
```javascript
// Use React Query's custom mutator
const client = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: async ({ queryKey }) => {
        return await customFetch(queryKey)
      }
    }
  }
})
```

**Why Not**: Mixes concerns. React Query handles caching. Axios handles HTTP. Keep them separate.

---

## Architecture Decision 3: React Query (TanStack Query) for Server State

### The Decision
Use **@tanstack/react-query** (React Query v5) for server state management.

```javascript
// ✅ React Query:
const { data, isLoading, error } = useQuery({
  queryKey: ['emissions'],
  queryFn: () => apiClient.get('/emissions/')
})

// ❌ NOT useState + useEffect:
const [data, setData] = useState(null)
const [loading, setLoading] = useState(true)
useEffect(() => {
  apiClient.get('/emissions/').then(r => setData(r.data))
}, [])
// Manual caching, refetch, errors
```

### Why This Decision

**Automatic Caching**: React Query caches by queryKey. Two components request same data → Only one API call.

**Stale-While-Revalidate**: Old data shows instantly while fresh data loads in background.

**Deduplication**: Multiple simultaneous requests for same key = one network call.

**Invalidation**: After mutation (upload, approve), invalidate related queries → Auto-refetch.

**Status Tracking**: isLoading, error, isPending all built-in. useState + useEffect requires manual tracking.

### Common Patterns

**Fetch data**:
```javascript
const { data: records } = useQuery({
  queryKey: ['emissions', { year: 2023 }],
  queryFn: () => apiClient.get('/emissions/?year=2023')
})
```

**Paginated data**:
```javascript
const { data: page } = useQuery({
  queryKey: ['emissions', { page: 1 }],
  queryFn: () => apiClient.get(`/emissions/?page=${page}`)
})
```

**Mutations (POST/PATCH)**:
```javascript
const { mutate, isPending } = useMutation({
  mutationFn: (taskId) => apiClient.post(`/review/${taskId}/approve/`),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['reviewTasks'] })
  }
})
```

### Alternative Considered: Redux Toolkit
```javascript
// Redux store + slices + thunks
dispatch(fetchEmissions())
// Boilerplate: actions, reducers, slices
```

**Why Not**: Overkill for this app. React Query + localStorage for tokens is 80% of what Redux provides, with 20% of complexity.

---

## Architecture Decision 4: JWT Token Storage in localStorage

### The Decision
Store JWT tokens in **localStorage** (not sessionStorage or cookies).

```javascript
// On login
localStorage.setItem('access_token', response.access)
localStorage.setItem('refresh_token', response.refresh)

// On request
const token = localStorage.getItem('access_token')
apiClient.defaults.headers['Authorization'] = `Bearer ${token}`
```

### Why This Decision

**Persistence**: Tokens survive page refresh. User doesn't re-login on F5.

**Access from JavaScript**: Can read/write in hooks. Cookies require secure flag (limits JS access).

**Simple**: No server-side session needed. JWT is self-contained.

**XSS Risk Mitigation**: Not perfect (localStorage is vulnerable to XSS), but:
  - No sensitive data besides token in localStorage
  - Backend should use HttpOnly cookies for enhanced security (Phase 3.2+)
  - For MVP, localStorage is acceptable

### Refresh Token Rotation
```javascript
// Interceptor catches 401
→ POST /auth/refresh/ with refresh_token
→ Server returns new access_token
→ Retry original request
→ User stays logged in
```

### Alternative Considered: HttpOnly Cookies
```javascript
// Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Strict
// Browser automatically sends with requests
// But: Can't access in JS (can't manually attach to axios)
```

**Why Not (for now)**: Requires CSRF tokens, cookie configuration on backend. Save for Phase 3.2+.

---

## Architecture Decision 5: Custom Hooks for Domain Logic

### The Decision
Create domain-specific hooks: `useEmissions()`, `useIngestions()`, `useReviewTasks()`, `useAuth()`.

```javascript
// ✅ Custom hooks (Chunk 3.1):
export function useEmissions(year, status) {
  return useQuery({
    queryKey: ['emissions', { year, status }],
    queryFn: () => apiClient.get(`/emissions/?year=${year}&status=${status}`)
  })
}

// Usage in component:
function EmissionsList() {
  const { data, error } = useEmissions(2023, 'APPROVED')
}

// ❌ NOT inline in components:
function EmissionsList() {
  const { data } = useQuery({
    queryKey: ['emissions', ...],
    queryFn: () => apiClient.get(...)
  })
}
// Each component re-implements the same logic
```

### Why This Decision

**Reusability**: Multiple components use emissions data → Define once, import many times.

**Single Source of Truth**: Query logic in one place. Easier to update API endpoint.

**Testing**: Mock hook in tests. Don't need to mock API client.

**Encapsulation**: Component doesn't know HTTP details. Just calls `useEmissions()`.

### Hooks in Chunk 3.1

**`useAuth()`**: Login, logout, currentUser
**`useEmissions()`**: Fetch emissions, summary, export
**`useIngestions()`**: Upload, parse, normalize, status
**`useReviewTasks()`**: Fetch tasks, approve, reject

Each follows React Query pattern:
```javascript
useQuery({
  queryKey: [...],
  queryFn: async () => { ... },
  staleTime: 1000 * 60 // 1 minute
})
```

### Alternative Considered: Context API for Global State
```javascript
// Global auth context
const { user, login, logout } = useContext(AuthContext)
```

**Why Not (now)**: Context causes re-render of all consumers on change. React Query is better for this.

---

## Architecture Decision 6: Error Boundary + Error Handler Utilities

### The Decision
Use React Error Boundary component + `getErrorMessage()` utility for consistent error handling.

```javascript
// Error Boundary catches React errors
<ErrorBoundary>
  <App />
</ErrorBoundary>

// Error handler formats API errors
const message = getErrorMessage(error)
// e.g., "Unauthorized. Please log in."
```

### Why This Decision

**Graceful Degradation**: Uncaught React errors don't white-screen. Show error message instead.

**Consistent Format**: API returns different error shapes (detail, field errors). Utility normalizes to string.

**User Friendly**: Show "Unauthorized. Please log in." not "401 Unauthorized".

**Development**: Console logs full error. Production shows user-friendly message.

### Error Types Handled

**Network Error**:
```javascript
// No response (connection failed)
→ "Network error. Please check your connection."
```

**DRF Validation**:
```javascript
// { "email": ["Invalid email"] }
→ "email: Invalid email"
```

**HTTP Status**:
```javascript
// 401 Unauthorized
→ "Unauthorized. Please log in."
```

### Alternative Considered: No Error Boundary
```javascript
// Let React crash on error
// App white-screens
```

**Why Not**: Poor UX. Users see blank page. Better to show error message.

---

## Architecture Decision 7: Vite Proxy for Local Development

### The Decision
Use Vite's proxy config to forward `/api/*` to backend during development.

```javascript
// vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

### Why This Decision

**Same Origin**: Frontend and backend appear to be same server (http://localhost:3000/api). Avoids CORS issues in development.

**Simplified Headers**: No need for CORS headers or preflight requests during dev.

**Realistic**: Production setup: frontend served from same domain or CORS configured. Proxy simulates this.

### Production Setup
```javascript
// In prod, frontend is at example.com
// Backend is at api.example.com or example.com/api
// Configure CORS or use same domain
```

### Alternative Considered: Manual CORS Headers
```python
# Django settings.py
CORS_ALLOWED_ORIGINS = ['http://localhost:3000']
```

**Why Not (for MVP)**: Works, but proxy is simpler. No extra CORS config needed.

---

## Architecture Decision 8: React Router for Client-Side Navigation

### The Decision
Use **react-router-dom** v6 for routing.

```javascript
// App.jsx
<BrowserRouter>
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
  </Routes>
</BrowserRouter>

// ProtectedRoute redirects to /login if not authenticated
```

### Why This Decision

**SPA Navigation**: Route changes don't reload page. Instant navigation.

**Protected Routes**: Wrap routes that require authentication. Auto-redirect to /login if not authenticated.

**Nested Routes**: Can nest routes (e.g., /review/{id}, /review/{id}/details).

**History API**: Uses browser history. Back button works.

### Route Structure (Phase 3.2+)
```
/login                 → LoginPage
/dashboard             → DashboardPage (summary, stats)
/upload                → UploadPage (CSV upload, parse, normalize)
/review                → ReviewPage (list of tasks)
/review/{id}           → ReviewDetailPage (single task)
/emissions             → EmissionsPage (view all emissions)
/settings              → SettingsPage (user profile, etc.)
```

### Alternative Considered: Server-Side Routing (Next.js)
```javascript
// pages/dashboard.js
export default function Dashboard() { ... }
// Automatic routing, server-side rendering
```

**Why Not**: Added complexity. Plain React + Router is simpler for this project.

---

## Architecture Decision 9: No State Management (Lift State Up Initially)

### The Decision
Don't install Redux, Zustand, or Recoil. Use React hooks + React Query.

```javascript
// Instead of Redux:
// - useEmissions() for server state (React Query)
// - useState() for component state (UI form, modals)
// - useAuth() for auth state (React Query)
```

### Why This Decision

**YAGNI (You Aren't Gonna Need It)**: Redux adds files (actions, reducers, selectors, middleware). Wait until you actually need global state.

**React Query Handles 80%**: Caching, synchronization, invalidation. What Redux was used for historically.

**Simple Props Passing**: For now, pass data down via props. If drilling gets annoying (3+ levels), extract to custom hook.

**Easy to Add Later**: If state complexity grows, add Redux/Zustand without rearchitecting.

### Example: Form State
```javascript
// Component manages form state locally
const [formData, setFormData] = useState({ year: 2023, status: 'APPROVED' })

// Pass down as props (or extract to useForm hook)
<EmissionsList formData={formData} />
```

### When to Add Global State
If you need:
- UI state shared across 5+ components (dark mode toggle)
- Complex interdependent state (filters affecting multiple sections)
- Undo/redo functionality
- Persisted client state

Then: Install Zustand (lighter than Redux) or Recoil.

### Alternative Considered: Redux from Day 1
```javascript
// dispatch(setYear(2023))
// dispatch(setStatus('APPROVED'))
// const { year, status } = useSelector(state => state.filters)
// 200 lines of boilerplate for simple state
```

**Why Not**: Boilerplate-heavy. Wait until needed.

---

## Architecture Decision 10: Environment Variables for API URL

### The Decision
Use `VITE_API_URL` environment variable for API base URL.

```javascript
// src/api/client.js
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// .env.development
VITE_API_URL=http://localhost:8000/api

// .env.production
VITE_API_URL=https://api.breathe.example.com
```

### Why This Decision

**Environment Switching**: Same build, different API endpoints (dev, staging, prod).

**No Hardcoding**: Endpoint isn't hardcoded in source code.

**Security**: Production API URL isn't in git history (add .env to .gitignore).

### Build-Time Variables
Vite replaces `import.meta.env.VITE_*` at build time. Secure (no sensitive data in browser at runtime).

### .env Files
```
.env.development  → npm run dev
.env.production   → npm run build
.env.local        → Local overrides (git-ignored)
```

### Alternative Considered: Runtime Configuration
```javascript
// fetch('/config.json') at app startup
// Get API URL from JSON file
```

**Why Not**: Extra network request on startup. Build-time vars are faster.

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Vite** | Fast, modern, simple config | Smaller ecosystem than CRA/Next.js |
| **Axios** | Centralized interceptors, error handling | One more dependency (vs. fetch) |
| **React Query** | Automatic caching, deduplication, invalidation | Learning curve (but worth it) |
| **localStorage** | Persistence, simple | XSS risk (mitigated with HTTPS, CSP) |
| **Custom Hooks** | Reusability, testability, encapsulation | Need discipline to avoid prop drilling |
| **Error Boundary** | Graceful degradation | Only catches React errors, not async errors |
| **Vite Proxy** | No CORS issues in dev | Only works in dev (not prod) |
| **React Router** | Client-side navigation, protected routes | Slightly more boilerplate than plain React |
| **No Redux** | Simplicity, YAGNI | May need to add later if state grows |
| **Environment Variables** | Config flexibility, security | Build-time only (not runtime) |

---

This chunk provides the foundation for Phase 3.2+ page development. All HTTP communication goes through `apiClient`. All data fetching uses React Query hooks. All errors go through `getErrorMessage()`. No page implementations yet—just the plumbing.

