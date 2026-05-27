# Chunk 3.2: Login & Authentication UI - Integration Guide

## Overview

This guide covers login page implementation, authentication flow, token management, protected route setup, and common authentication patterns.

---

## Setup & Integration

### 1. Update App.jsx Routes

LoginPage and NavBar are already integrated in App.jsx:

```javascript
// src/App.jsx
import LoginPage from './pages/LoginPage'
import NavBar from './components/NavBar'

function App() {
  return (
    <Router>
      <Routes>
        {/* Public login route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes with navbar */}
        <Route path="/*" element={
          <ProtectedRoute>
            <>
              <NavBar />
              {/* Other pages go here */}
            </>
          </ProtectedRoute>
        } />
      </Routes>
    </Router>
  )
}
```

### 2. Demo Credentials (Development)

Use these credentials to test login:

```
Username: alice
Password: password123

OR

Username: bob
Password: password123
```

These are created in Django fixture (Chunk 2.3 test setup).

### 3. Run Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
# → http://localhost:3000/login automatically displayed (no token)
```

---

## Example 1: Login Flow

### Manual Step-by-Step

```
1. Go to http://localhost:3000/login
2. See login form with:
   - Username input
   - Password input
   - Demo credentials (alice, password123)
   - Login button

3. Enter username: alice
4. Enter password: password123
5. Click Login

6. Frontend:
   - POST /api/auth/login/ with {username, password}
   - Receives {access_token, refresh_token}
   - Stores in localStorage
   - Redirects to /dashboard

7. See:
   - NavBar with "alice (Acme Corp)"
   - Logout button
   - Dashboard content (placeholder)

8. Refresh page (F5)
   - Token still in localStorage
   - App loads dashboard (not login)
   - User stays logged in
```

---

## Example 2: Form Validation

### Username Validation

```javascript
// User enters username
1. Typing "a" → No error shown (not touched yet)
2. Leave field (blur) → Touched
3. See error if empty (won't happen here, "a" is present)
4. Typing more → Error hidden (field has value)
5. Clear field → Still no error (leave field)
6. Re-focus and blur empty → Error shows "Username required"
```

### Password Validation

Same pattern as username:
```javascript
1. Focus password field
2. Type nothing, blur → Error: "Password required"
3. Type something → Error hidden
4. Clear and blur → Error shows again
```

### Submit Validation

```javascript
// User clicks Login without filling form
1. Both fields empty
2. Click Login
3. Button doesn't submit
4. Both fields marked touched
5. Errors shown: "Username required", "Password required"
6. User fills in values
7. Errors disappear
8. Can click Login
```

---

## Example 3: Error Handling

### Invalid Credentials

```javascript
// User enters valid username but wrong password
1. Username: alice
2. Password: wrongpassword
3. Click Login
4. Backend returns 401: "Invalid credentials"
5. Frontend displays:
   - Alert box with red background
   - Message: "Unauthorized. Please log in."
   - Button re-enabled
   - User can retry

// Try again with correct password
1. Password: password123
2. Click Login
3. Success → Redirect to dashboard
```

### Network Error

```javascript
// Backend is down
1. User clicks Login
2. Network timeout (no response)
3. Frontend displays:
   - Alert box with red background
   - Message: "Network error. Please check your connection."
   - Button re-enabled
   - User can retry
```

### Server Error

```javascript
// Backend returns 500
1. User clicks Login
2. Backend returns 500: "Internal Server Error"
3. Frontend displays:
   - Alert box
   - Message: "Server error. Please try again later."
   - User can retry
```

---

## Example 4: Token Persistence

### Scenario: Login and Refresh

```javascript
// Step 1: Login and get token
1. POST /api/auth/login/ with {username: alice, password: password123}
2. Response: {
     "access": "eyJhbGc...",
     "refresh": "eyJhbGc...",
     "user": { "id": 1, "username": "alice" }
   }
3. Frontend stores:
   localStorage.setItem('access_token', 'eyJhbGc...')
   localStorage.setItem('refresh_token', 'eyJhbGc...')

// Step 2: User refreshes page (F5)
1. App starts
2. ProtectedRoute checks: localStorage.getItem('access_token')
3. Token present → Doesn't redirect to login
4. useCurrentUser() hook fetches /api/auth/me/
5. Backend validates token
6. Returns user profile
7. NavBar renders with username
8. User stays logged in

// Step 3: User closes browser, reopens next day
1. Tokens still in localStorage
2. access_token expired (1 hour ago)
3. useCurrentUser() fails with 401
4. ProtectedRoute redirects to /login
5. User logs in again

// Step 4: Automatic Token Refresh
1. User logged in 55 minutes ago
2. access_token will expire in 5 minutes
3. User makes request (e.g., fetch emissions)
4. API client adds: Authorization: Bearer {old_token}
5. Backend returns 401 (token expired)
6. apiClient interceptor catches 401
7. Sends POST /api/auth/refresh/ with {refresh_token}
8. Backend returns new {access_token}
9. apiClient stores new token
10. Retries original request with new token
11. Request succeeds
12. User sees data (no interruption)
```

---

## Example 5: Logout Flow

### Step-by-Step

```javascript
// User logged in, sees NavBar
1. See username "alice" in NavBar
2. See "Logout" button
3. Click Logout

// Frontend logout flow
1. NavBar LogoutButton sends mutate: logout()
2. useLogout() hook:
   - POST /api/auth/logout/ (optional, for audit)
   - Clear localStorage tokens
   - Clear all React Query caches
   - Redirect to /login

// Result
1. Browser navigates to /login
2. ProtectedRoute checks for token
3. No token → Allows login page
4. User sees login form
5. Session cleared
```

---

## Example 6: Protected Routes

### Route Guard Logic

```javascript
// ProtectedRoute component (src/components/ProtectedRoute.jsx)

function ProtectedRoute({ children }) {
  const { data: user, isLoading, error } = useCurrentUser()
  const token = localStorage.getItem('access_token')

  // No token → Redirect to login
  if (!token) {
    return <Navigate to="/login" replace />
  }

  // Loading user data
  if (isLoading) {
    return <div>Loading...</div>
  }

  // Token invalid/expired → Clear and redirect
  if (error) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return <Navigate to="/login" replace />
  }

  // All checks passed → Render protected page
  return children
}
```

### Protected Route Usage

```javascript
// Public page (no guard)
<Route path="/login" element={<LoginPage />} />

// Protected page (guard applied)
<Route path="/dashboard" element={
  <ProtectedRoute>
    <DashboardPage />
  </ProtectedRoute>
} />

// If user not logged in
1. Visit /dashboard
2. ProtectedRoute checks token
3. No token → Redirect to /login

// If user logged in
1. Visit /dashboard
2. ProtectedRoute checks token
3. Token present → Load user profile
4. Profile loaded successfully → Render DashboardPage
5. Profile fails to load → Clear token, redirect to /login
```

---

## Example 7: NavBar Integration

### Display User Info

```javascript
// NavBar shows (from useCurrentUser hook)
- Username: "alice"
- Tenant: "(Acme Corp)"
- Logout button

// Data comes from /api/auth/me/
{
  "id": 1,
  "username": "alice",
  "email": "alice@acme.com",
  "tenant_name": "Acme Corp",
  "role": "ANALYST"
}
```

### Logout Handler

```javascript
// Click logout button
1. NavBar calls: logout()
2. useLogout() mutation executes
3. Backend clears audit log (logout event)
4. Frontend clears localStorage
5. Frontend clears React Query cache
6. Frontend redirects to /login
7. User must log in again
```

---

## Example 8: Multi-Tenant Context

### Tenant-Aware Features

LoginPage doesn't show tenant selection (uses default tenant from JWT claims):

```javascript
// JWT contains tenant_id
{
  "user_id": 1,
  "username": "alice",
  "tenant_id": 1  // Acme Corp
}

// All subsequent requests auto-filtered by tenant
GET /api/emissions/
// Backend: WHERE tenant_id = user.tenant_id
// Returns: Only Acme Corp emissions

GET /api/ingest/
// Backend: WHERE tenant_id = user.tenant_id
// Returns: Only Acme Corp ingestions
```

### Tenant Display

NavBar shows tenant from user profile:

```javascript
// User profile from /api/auth/me/
{
  "username": "alice",
  "tenant_name": "Acme Corp"
}

// NavBar renders
alice (Acme Corp)
```

---

## Example 9: Session Timeout

### Token Expiration Handling

```javascript
// Token expires after 1 hour (default Django Simplejwt)

// Scenario 1: Token expires while user idle
1. User logs in at 10:00
2. User leaves page open
3. At 11:00, access_token expires
4. User returns and clicks a button
5. API call with expired token
6. Backend returns 401
7. Interceptor refreshes token automatically
8. Request retried
9. User sees no error

// Scenario 2: Token expires, refresh token also invalid
1. User logs in
2. Both tokens expire (refresh token = 7 days)
3. User tries to use app
4. API call with expired token
5. Backend returns 401
6. Interceptor tries refresh
7. Refresh fails (refresh token also expired)
8. Interceptor redirects to /login
9. User must log in again
```

### Token Refresh Endpoint

LoginPage doesn't directly call refresh. It's automatic:

```javascript
// /api/auth/refresh/ (handled by interceptor)
POST /api/auth/refresh/
{
  "refresh": "eyJhbGc..."
}

// Response
{
  "access": "eyJhbGc..."
}

// Interceptor stores new access token and retries request
```

---

## Example 10: Credential Variations

### Test Different Users

Test multi-tenancy:

```javascript
// Login as Alice (Tenant: Acme Corp)
Username: alice
Password: password123
// See: "alice (Acme Corp)"

// Logout
// Click Logout button

// Login as Bob (Tenant: Beta Inc)
Username: bob
Password: password123
// See: "bob (Beta Inc)"

// Data is tenant-specific
- Alice's emissions (Acme Corp only)
- Bob's emissions (Beta Inc only)
- Neither can see the other's data
```

### Test Admin vs Analyst

(Both alice and bob have ANALYST role in Chunk 2.3)

In Phase 3.3+, features will check roles:

```javascript
// Example (not in 3.2, but coming)
if (user.role === 'ANALYST') {
  // Show review page
}
if (user.role === 'ADMIN') {
  // Show admin settings
}
```

---

## File Structure

```
frontend/
├── src/
│   ├── pages/
│   │   └── LoginPage.jsx           # Login form + validation
│   ├── components/
│   │   ├── ProtectedRoute.jsx      # Route guard (from 3.1)
│   │   ├── NavBar.jsx              # Header with user info + logout (NEW)
│   │   └── ErrorBoundary.jsx       # Error boundary (from 3.1)
│   ├── hooks/
│   │   └── useAuth.js              # useLogin, useLogout, useCurrentUser (from 3.1)
│   ├── App.jsx                     # Routes: /login + protected routes
│   └── index.css                   # Styles including @keyframes spin
```

---

## Testing Checklist

### Manual Testing

- [ ] Navigate to http://localhost:3000/login
- [ ] See LoginPage with form and demo credentials
- [ ] Enter invalid credentials, see "Unauthorized" error
- [ ] Enter valid credentials (alice/password123), see success
- [ ] Redirected to /dashboard
- [ ] See NavBar with "alice (Acme Corp)" and Logout button
- [ ] Refresh page (F5) → Stay logged in (token persists)
- [ ] Click Logout → Redirect to /login
- [ ] Token cleared from localStorage
- [ ] Try to visit /dashboard → Redirected to /login (no token)

### Form Validation Testing

- [ ] Leave username empty, blur → See "Username required"
- [ ] Fill username, error disappears
- [ ] Leave password empty, blur → See "Password required"
- [ ] Fill password, error disappears
- [ ] Click Login with both empty → Show both errors, don't submit
- [ ] Click Login with correct credentials → No errors, submit succeeds

### Multi-Tenant Testing

- [ ] Login as alice → See "Acme Corp"
- [ ] Logout
- [ ] Login as bob → See "Beta Inc"
- [ ] Logout

### Error Scenarios

- [ ] Backend down: See "Network error..."
- [ ] Wrong password: See "Unauthorized..."
- [ ] Server error (500): See "Server error..."

---

## Code Examples for Other Components

### Using Auth in Other Pages

```javascript
// src/pages/DashboardPage.jsx
import { useCurrentUser } from '../hooks/useAuth'

export function DashboardPage() {
  const { data: user } = useCurrentUser()

  return (
    <div>
      <h1>Welcome, {user?.username}!</h1>
      <p>Tenant: {user?.tenant_name}</p>
    </div>
  )
}
```

### Checking User Role

```javascript
// src/pages/AdminPage.jsx
import { useCurrentUser } from '../hooks/useAuth'

export function AdminPage() {
  const { data: user, isLoading } = useCurrentUser()

  if (isLoading) return <div>Loading...</div>

  if (user?.role !== 'ADMIN') {
    return <div>Access denied. Admins only.</div>
  }

  return <div>Admin settings...</div>
}
```

### Conditional Navigation Based on Role

```javascript
// src/components/NavBar.jsx
import { useCurrentUser } from '../hooks/useAuth'

function NavBar() {
  const { data: user } = useCurrentUser()

  return (
    <nav>
      <a href="/dashboard">Dashboard</a>
      <a href="/review">Review</a>
      {user?.role === 'ADMIN' && <a href="/settings">Admin</a>}
    </nav>
  )
}
```

---

## Next Steps (Phase 3.3)

Chunk 3.2 completes login. Phase 3.3+ adds:
- **3.3**: Dashboard page (summary metrics, charts)
- **3.4**: Upload page (file upload, parsing, normalization)
- **3.5**: Review page (approve/reject tasks)
- **3.6**: Emissions list page (filtering, export)

All pages will use `useCurrentUser()` to verify user is authenticated and access tenant context.

---

This chunk completes the authentication layer. Users can now securely log in, stay logged in across sessions, and log out. All subsequent pages inherit authenticated context.

