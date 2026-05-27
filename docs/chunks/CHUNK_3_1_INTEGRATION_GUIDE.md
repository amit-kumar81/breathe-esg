# Chunk 3.1: React Project Setup & API Client - Integration Guide

## Overview

This guide covers setup, API client usage, React Query integration, authentication flow, and common patterns for building pages on top of Chunk 3.1's foundation.

---

## Setup Instructions

### 1. Install Dependencies

```bash
cd frontend
npm install
# Installs: react, react-dom, react-router-dom, @tanstack/react-query, axios
```

### 2. Create Environment File

```bash
cp .env.example .env.development
# Or for production:
cp .env.example .env.production
```

### 3. Configure Backend API URL

Edit `.env.development`:
```
VITE_API_URL=http://localhost:8000/api
```

For production `.env.production`:
```
VITE_API_URL=https://api.example.com
```

### 4. Run Development Server

```bash
npm run dev
# Starts: http://localhost:3000
# Proxy: http://localhost:3000/api → http://localhost:8000/api
```

### 5. Build for Production

```bash
npm run build
# Output: dist/
# Upload dist/ to web server
```

---

## Example 1: Using the API Client Directly

For simple one-off API calls:

```javascript
// src/pages/ExamplePage.jsx
import { apiClient } from '../api/client'
import { useState, useEffect } from 'react'

export function ExamplePage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiClient.get('/emissions/summary/')
      .then(response => setData(response.data))
      .catch(err => setError(err.message))
  }, [])

  if (error) return <div>Error: {error}</div>
  if (!data) return <div>Loading...</div>

  return (
    <div>
      <h1>Summary</h1>
      <p>Total Records: {data.total_records}</p>
    </div>
  )
}
```

---

## Example 2: Using React Query Hook

Preferred approach (caching, auto-retry, deduplication):

```javascript
// src/pages/EmissionsPage.jsx
import { useEmissions } from '../hooks/useEmissions'
import { useState } from 'react'

export function EmissionsPage() {
  const [year, setYear] = useState(2023)
  const [status, setStatus] = useState('APPROVED')

  // useEmissions automatically:
  // - Caches results by queryKey
  // - Retries on failure
  // - Handles loading/error states
  const { data, isLoading, error } = useEmissions({
    year,
    statusFilter: status
  })

  if (isLoading) return <div>Loading emissions...</div>
  if (error) return <div>Error: {error.message}</div>
  if (!data) return <div>No data</div>

  return (
    <div>
      <h1>Emissions Records</h1>
      <div>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          <option value={2023}>2023</option>
          <option value={2022}>2022</option>
        </select>

        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="APPROVED">Approved</option>
          <option value="PENDING">Pending</option>
        </select>
      </div>

      <table>
        <thead>
          <tr>
            <th>Facility</th>
            <th>Scope 1</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {data.results?.map(record => (
            <tr key={record.id}>
              <td>{record.facility_name}</td>
              <td>{record.scope_1_emissions}</td>
              <td>{record.review_status}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p>Showing {data.results?.length} of {data.count} records</p>
    </div>
  )
}
```

---

## Example 3: Using Mutations (POST/PATCH)

For actions that modify data:

```javascript
// src/pages/ReviewPage.jsx
import { useReviewTaskDetail, useApproveTask, useRejectTask } from '../hooks/useReviewTasks'
import { useState } from 'react'

export function ReviewPage({ taskId }) {
  const { data: task, isLoading } = useReviewTaskDetail(taskId)
  const { mutate: approve, isPending: isApproving } = useApproveTask(taskId)
  const { mutate: reject, isPending: isRejecting } = useRejectTask(taskId)
  const [notes, setNotes] = useState('')

  if (isLoading) return <div>Loading...</div>
  if (!task) return <div>Task not found</div>

  return (
    <div>
      <h1>{task.normalized_record.facility_name}</h1>
      <p>Scope 1: {task.normalized_record.scope_1_emissions}</p>
      <p>Quality Score: {task.data_quality_score}</p>

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Approval notes..."
      />

      <button
        onClick={() => approve(notes)}
        disabled={isApproving}
      >
        {isApproving ? 'Approving...' : 'Approve'}
      </button>

      <button
        onClick={() => reject('Data quality issues')}
        disabled={isRejecting}
      >
        {isRejecting ? 'Rejecting...' : 'Reject'}
      </button>
    </div>
  )
}
```

---

## Example 4: Handling Authentication

Login flow:

```javascript
// src/pages/LoginPage.jsx
import { useLogin } from '../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

export function LoginPage() {
  const navigate = useNavigate()
  const { mutate: login, isPending, error } = useLogin()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    login(
      { username, password },
      {
        onSuccess: () => {
          // Login succeeded, redirect to dashboard
          navigate('/dashboard')
        }
      }
    )
  }

  return (
    <div>
      <h1>Login</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button type="submit" disabled={isPending}>
          {isPending ? 'Logging in...' : 'Login'}
        </button>
      </form>
      {error && <div style={{ color: 'red' }}>{error.message}</div>}
    </div>
  )
}
```

---

## Example 5: File Upload (CSV)

```javascript
// src/pages/UploadPage.jsx
import { useUploadCSV } from '../hooks/useIngestions'
import { useState } from 'react'

export function UploadPage() {
  const { mutate: upload, isPending, data } = useUploadCSV()
  const [file, setFile] = useState(null)
  const [dataSourceId, setDataSourceId] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (file && dataSourceId) {
      upload({ file, dataSourceId })
    }
  }

  return (
    <div>
      <h1>Upload CSV</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept=".csv"
          onChange={(e) => setFile(e.target.files?.[0])}
        />
        <input
          type="text"
          placeholder="Data Source ID"
          value={dataSourceId}
          onChange={(e) => setDataSourceId(e.target.value)}
        />
        <button type="submit" disabled={isPending || !file}>
          {isPending ? 'Uploading...' : 'Upload'}
        </button>
      </form>

      {data && (
        <div>
          <p>✓ Upload successful!</p>
          <p>Ingestion ID: {data.id}</p>
          <p>Status: {data.step}</p>
        </div>
      )}
    </div>
  )
}
```

---

## Example 6: Error Handling

Extracting and displaying errors:

```javascript
// src/pages/SafePage.jsx
import { useEmissions } from '../hooks/useEmissions'
import { getErrorMessage } from '../utils/errorHandler'

export function SafePage() {
  const { data, error, isLoading } = useEmissions()

  if (isLoading) return <div>Loading...</div>

  if (error) {
    const message = getErrorMessage(error)
    return (
      <div style={{
        padding: '20px',
        backgroundColor: '#f8d7da',
        color: '#721c24',
        borderRadius: '4px'
      }}>
        <h2>Something went wrong</h2>
        <p>{message}</p>
      </div>
    )
  }

  return (
    <div>
      <h1>Emissions</h1>
      <p>Total: {data?.count}</p>
    </div>
  )
}
```

---

## Example 7: Pagination

```javascript
// src/components/PaginatedTable.jsx
import { useEmissions } from '../hooks/useEmissions'
import { useState } from 'react'

export function PaginatedTable() {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useEmissions({ page })

  if (isLoading) return <div>Loading...</div>

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Facility</th>
            <th>Emissions</th>
          </tr>
        </thead>
        <tbody>
          {data?.results?.map(r => (
            <tr key={r.id}>
              <td>{r.facility_name}</td>
              <td>{r.scope_1_emissions}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div>
        <button
          onClick={() => setPage(p => p - 1)}
          disabled={page === 1 || !data?.previous}
        >
          Previous
        </button>
        <span>Page {page} of {Math.ceil(data?.count / 20)}</span>
        <button
          onClick={() => setPage(p => p + 1)}
          disabled={!data?.next}
        >
          Next
        </button>
      </div>
    </div>
  )
}
```

---

## Example 8: Optimistic Updates

Update UI before server responds:

```javascript
// src/components/TaskApprovalButton.jsx
import { useApproveTask } from '../hooks/useReviewTasks'
import { useQueryClient } from '@tanstack/react-query'

export function TaskApprovalButton({ taskId, onSuccess }) {
  const queryClient = useQueryClient()
  const { mutate } = useApproveTask(taskId)

  const handleApprove = () => {
    // Optimistically update cache
    queryClient.setQueryData(
      ['reviewTasks', taskId],
      (old) => ({ ...old, review_status: 'APPROVED' })
    )

    // Send to server
    mutate(null, {
      onError: () => {
        // Revert on error
        queryClient.invalidateQueries({ queryKey: ['reviewTasks', taskId] })
      }
    })
  }

  return <button onClick={handleApprove}>Approve</button>
}
```

---

## Example 9: Dependent Queries

Fetch data only when condition is met:

```javascript
// src/components/TaskReview.jsx
import { useReviewTaskDetail, useEmissionDetail } from '../hooks'

export function TaskReview({ taskId }) {
  // Fetch task
  const { data: task } = useReviewTaskDetail(taskId)

  // Fetch full emission details only if task exists
  const { data: emission } = useEmissionDetail(
    task?.emissions_data_point_id,
    { enabled: !!task?.emissions_data_point_id } // Only fetch if we have ID
  )

  return (
    <div>
      {task && <h1>{task.normalized_record.facility_name}</h1>}
      {emission && <p>Full history: {emission.audit_trail.length} changes</p>}
    </div>
  )
}
```

---

## Example 10: Token Refresh Automatic Handling

The API client automatically handles expired tokens:

```javascript
// No special code needed!
// If token expires:
// 1. Request fails with 401
// 2. Interceptor refreshes token
// 3. Original request retried
// 4. User sees no interruption

const { data } = useEmissions() // Works seamlessly with expired tokens
```

---

## File Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.js              # Axios instance + interceptors
│   ├── hooks/
│   │   ├── useAuth.js             # Login, logout, current user
│   │   ├── useEmissions.js        # Fetch emissions, export
│   │   ├── useIngestions.js       # Upload, parse, normalize
│   │   └── useReviewTasks.js      # Fetch tasks, approve/reject
│   ├── components/
│   │   ├── ErrorBoundary.jsx      # Error boundary wrapper
│   │   └── ProtectedRoute.jsx     # Route guard for authenticated pages
│   ├── utils/
│   │   └── errorHandler.js        # Error message formatting
│   ├── App.jsx                    # Main app + routing
│   ├── main.jsx                   # Entry point
│   └── index.css                  # Basic styles
├── index.html                     # HTML entry
├── vite.config.js                 # Vite config with proxy
├── package.json                   # Dependencies
├── .env.example                   # Environment template
└── .env.development               # Development config (git-ignored)
```

---

## Common Patterns

### Pattern 1: Loading State
```javascript
const { isLoading, data } = useEmissions()
if (isLoading) return <Spinner />
```

### Pattern 2: Error Handling
```javascript
const { error } = useEmissions()
if (error) return <Alert>{getErrorMessage(error)}</Alert>
```

### Pattern 3: Refresh on Mount
```javascript
const queryClient = useQueryClient()
useEffect(() => {
  queryClient.invalidateQueries({ queryKey: ['emissions'] })
}, [])
```

### Pattern 4: Conditional Fetch
```javascript
const { data } = useEmissions({
  enabled: !!selectedYear // Only fetch if year is selected
})
```

### Pattern 5: Auto-Refetch After Mutation
```javascript
useMutation({
  mutationFn: (data) => apiClient.post('/review/approve/', data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['reviewTasks'] })
  }
})
```

---

## Testing Setup (Future)

Chunk 3.1 is ready for unit/integration tests via:
- **vitest** for unit tests (replace jest)
- **@testing-library/react** for component tests
- **msw** (Mock Service Worker) to mock API responses

No tests included in 3.1 (focus on setup), but hooks are designed to be testable:

```javascript
// Example test (not in 3.1, but doable):
import { renderHook, waitFor } from '@testing-library/react'
import { useEmissions } from './useEmissions'

test('useEmissions fetches data', async () => {
  const { result } = renderHook(() => useEmissions())

  await waitFor(() => expect(result.current.data).toBeDefined())
  expect(result.current.data.count).toBeGreaterThan(0)
})
```

---

## Next Steps (Phase 3.2)

Chunk 3.1 is foundational. Phase 3.2+ builds pages:
- **3.2**: Dashboard page (useEmissionsSummary, charts)
- **3.3**: Upload page (useUploadCSV, useParse, useNormalize)
- **3.4**: Review page (useReviewTasks, useApproveTask)
- **3.5**: Login page (useLogin, useLogout)
- **3.6**: Emissions list page (useEmissions with filtering)

All pages will use hooks from 3.1 with zero API client changes.

---

This chunk provides the plumbing for the frontend. All data flows through React Query. All HTTP goes through the centralized API client. All errors are formatted consistently. Pages (3.2+) are now simple.

