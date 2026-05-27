# Chunk 3.2: Login & Authentication UI - Detailed Explanation

## Overview

Chunk 3.2 implements a complete login page with form validation, error handling, and session persistence. Uses the `useLogin()` hook from 3.1 and integrates with JWT token management. Also adds a navigation bar for authenticated users with logout functionality.

---

## Architecture Decision 1: Form Validation (Client-Side Only, No Backend Validation Display)

### The Decision
Validate form fields **client-side before submission** (username/password required). Display API validation errors from backend.

```javascript
// ✅ Client-side validation (3.2):
if (!username || !password) {
  setTouched({ username: true, password: true })
  return // Don't submit empty form
}

// On API error, display backend message:
{error && <div>{getErrorMessage(error)}</div>}

// ❌ NOT server-only validation:
// Submit empty form, wait for 400 response, show error
// Better UX: validate before hitting server
```

### Why This Decision

**User Experience**: Instant feedback. User sees "Username required" without network delay.

**Bandwidth**: Don't waste API call on obviously invalid input (empty fields).

**Server Load**: Fewer failed requests.

**Accessibility**: Error messages appear on blur, guiding the user.

### Validation Rules
```javascript
- username: Required, non-empty
- password: Required, non-empty
- (Other rules handled by backend)
```

### Backend Validation
Backend still validates (bad username, wrong password, user inactive). Frontend displays these errors:
```javascript
// 401 response: "Invalid credentials"
// Display: "Unauthorized. Please log in."
```

### Alternative Considered: No Client-Side Validation
```javascript
// Submit any form state
login({ username: '', password: '' })
// Wait for 400 response
```

**Why Not**: Poor UX. Network latency before feedback. Better to validate instantly.

---

## Architecture Decision 2: Inline Styles vs. CSS Classes

### The Decision
Use **inline styles** for LoginPage styling. Scoped styles object at bottom of component.

```javascript
// ✅ Inline styles (3.2):
<div style={styles.container}>
  <input style={styles.input} />
</div>

const styles = {
  container: { ... },
  input: { ... }
}

// ❌ NOT separate CSS file:
// <div className="login-container">
// <input className="login-input" />
// // + separate LoginPage.css
```

### Why This Decision

**Encapsulation**: Styles are co-located with component. Easy to see what's styled.

**No CSS Conflicts**: No global scope pollution. Styles die when component unmounts.

**Self-Contained**: LoginPage.jsx is a complete unit—no hunting for CSS files.

**Smaller MVP**: No CSS build step needed.

### Hover States
```javascript
// Handle dynamic styles with event handlers:
onMouseOver={(e) => e.target.style.backgroundColor = '#c82333'}
onMouseOut={(e) => e.target.style.backgroundColor = '#dc3545'}
```

### When to Switch to CSS Modules
If pages grow complex:
```css
/* LoginPage.module.css */
.container { ... }
```
Then import and use. For MVP, inline is simpler.

### Alternative Considered: Tailwind CSS
```jsx
<div className="flex justify-center items-center min-h-screen bg-gray-100">
```

**Why Not**: Extra dependency. Inline styles are simpler for MVP.

---

## Architecture Decision 3: Controlled Form Inputs

### The Decision
Use React `useState()` for form state. Input values controlled by state.

```javascript
// ✅ Controlled inputs (3.2):
const [username, setUsername] = useState('')
<input value={username} onChange={(e) => setUsername(e.target.value)} />

// ❌ NOT uncontrolled:
<input ref={inputRef} />
// Access value via inputRef.current.value later
```

### Why This Decision

**React Best Practice**: React recommends controlled inputs.

**Realtime Validation**: Can validate as user types (if needed later).

**Preset Values**: Easy to populate from state (login as different user).

**Form Resets**: Clear form by setting state to empty strings.

### Form Reset Pattern
```javascript
const handleReset = () => {
  setUsername('')
  setPassword('')
  setTouched({})
}
```

### Alternative Considered: Uncontrolled Inputs
```javascript
const usernameRef = useRef()
const handleSubmit = () => {
  const username = usernameRef.current.value
}
```

**Why Not**: Less React-idiomatic. Harder to validate in realtime.

---

## Architecture Decision 4: Touched Fields for Validation Display

### The Decision
Show validation errors only for fields the user has interacted with (`touched` state).

```javascript
// ✅ Touched tracking (3.2):
const [touched, setTouched] = useState({})
<input onBlur={() => setTouched({...touched, [field]: true})} />

{touched.username && !username && <p>Username required</p>}

// ❌ NOT show all errors immediately:
// {!username && <p>Username required</p>}
// User sees error while typing first character
```

### Why This Decision

**Better UX**: User doesn't see errors before interacting. Typing first character doesn't show red error.

**Guidance Over Judgment**: "Username required" only appears after user focuses and leaves field.

**Progressive Disclosure**: Errors appear as user needs them.

### Touch Pattern
```javascript
<input
  onBlur={() => setTouched({...touched, username: true})}
/>
{touched.username && !username && <Error />}
```

### Alternative Considered: Show All Errors
```javascript
{!username && <p>Username required</p>}
// Error shows while user typing
```

**Why Not**: Too aggressive. Feels like app is judging user.

---

## Architecture Decision 5: Disabled Submit Button During Loading

### The Decision
Disable the submit button while login request is in-flight. Show "Logging in..." text.

```javascript
// ✅ Disabled during loading (3.2):
<button disabled={isPending} type="submit">
  {isPending ? 'Logging in...' : 'Login'}
</button>

// ❌ NOT allow multiple submissions:
// User can click button multiple times
// Multiple login requests fired
```

### Why This Decision

**Prevents Duplicate Submissions**: User clicks once, waits for response. Can't accidentally click twice.

**Feedback**: User sees "Logging in..." spinner. Knows request is happening.

**Graceful Degradation**: Button visually disabled (grayed out, cursor changes).

### Loading Indicator
```javascript
{isPending ? (
  <>
    <span style={styles.spinner}></span>
    Logging in...
  </>
) : (
  'Login'
)}
```

### Alternative Considered: Show Spinner Without Disabling
```javascript
<button type="submit">
  {isPending && <Spinner />} Login
</button>
// Button still clickable, sends multiple requests
```

**Why Not**: Risk of duplicate submissions.

---

## Architecture Decision 6: Redirect to Dashboard After Login

### The Decision
Use `navigate('/dashboard', { replace: true })` after successful login. Don't use back button.

```javascript
// ✅ Replace history (3.2):
login(credentials, {
  onSuccess: () => navigate('/dashboard', { replace: true })
})

// ❌ NOT push to history:
// navigate('/dashboard')
// User presses back → Returns to login (bad UX)
```

### Why This Decision

**Better UX**: User logs in, goes to dashboard. Pressing back doesn't return to login.

**History Cleanup**: Removes login page from browser history.

**Intent**: User should never return to login while authenticated (ProtectedRoute prevents it anyway).

### Navigation Flow
```
1. User at /login
2. User submits login form
3. Success → navigate('/dashboard', { replace: true })
4. Browser history: / → /dashboard (not /login → /dashboard)
5. User presses back → Goes to /, not /login
```

### Alternative Considered: Regular Push Navigation
```javascript
navigate('/dashboard')
// Back button → /login
```

**Why Not**: Confusing. User logs in, presses back, gets logged-out state.

---

## Architecture Decision 7: NavBar Component for Authenticated Users

### The Decision
Create separate `NavBar.jsx` component. Only display when user is authenticated (inside ProtectedRoute).

```javascript
// ✅ NavBar in authenticated zone (3.2):
<ProtectedRoute>
  <>
    <NavBar />
    <MainContent />
  </>
</ProtectedRoute>

// ❌ NOT show NavBar everywhere:
// <NavBar /> at top level
// Would show on login page (confusing)
```

### Why This Decision

**Separation of Concerns**: Login is separate flow. Authenticated pages are separate.

**Simpler NavBar**: Doesn't need to check if user is logged in. Only renders when authenticated.

**Cleaner Routing**: Public pages (login) don't have nav. Private pages do.

### NavBar Features
```javascript
- App logo/title
- Username display
- Tenant name (multi-tenancy context)
- Logout button
```

### Alternative Considered: Conditional NavBar
```javascript
{isAuthenticated && <NavBar />}
// Show NavBar on all pages conditionally
```

**Why Not**: More complex. NavBar would need to handle logged-out state.

---

## Architecture Decision 8: Demo Credentials Display

### The Decision
Show demo credentials (alice/bob, password123) on login page for development.

```javascript
// ✅ Show demo creds (3.2):
<div style={styles.info}>
  <p>Demo: alice / password123</p>
</div>

// ❌ NOT hidden:
// No way for testers to know credentials
```

### Why This Decision

**Developer Convenience**: Don't need to create test users or look them up.

**QA Efficiency**: Testers can quickly log in and test functionality.

**Development Speed**: New developers see creds immediately.

### Production Behavior
In `.env.production`, remove/comment out demo creds, or check environment:
```javascript
{process.env.NODE_ENV === 'development' && <DemoCreds />}
```

### Alternative Considered: No Demo Creds
```javascript
// Require actual user creation or test fixtures
// Slows down development
```

**Why Not**: Slows iteration. MVP benefits from easy login.

---

## Architecture Decision 9: Error Message from getErrorMessage() Utility

### The Decision
Use centralized `getErrorMessage()` for formatting API errors.

```javascript
// ✅ Centralized error formatting (3.2):
const message = getErrorMessage(error)
// Returns: "Invalid credentials" or "Network error..."

// ❌ NOT direct error display:
// {error?.response?.data?.detail}
// Inconsistent, raw API response
```

### Why This Decision

**Consistency**: Same error format across all pages.

**User-Friendly**: "Invalid credentials" instead of "401 Unauthorized".

**Maintainability**: Change error format once, updates everywhere.

**Internationalization**: Single place to add i18n later.

### Error Types Handled
- Network errors: "Network error. Please check your connection."
- 401: "Unauthorized. Please log in."
- Invalid credentials: "Invalid username/password"
- Server errors: "Server error. Please try again later."

### Alternative Considered: Inline Error Handling
```javascript
{error?.response?.status === 401 && <p>Unauthorized</p>}
{error?.response?.status === 500 && <p>Server Error</p>}
// On every page
```

**Why Not**: Repetitive. Centralized is better.

---

## Architecture Decision 10: Token Stored in localStorage Automatically

### The Decision
LoginPage doesn't manually store tokens. The `useLogin()` hook handles it.

```javascript
// ✅ Hook handles storage (3.2):
const { mutate: login } = useLogin()
// useLogin() internally calls localStorage.setItem()

// ❌ NOT manual storage:
// const response = await apiClient.post('/auth/login/')
// localStorage.setItem('access_token', response.access)
// Duplicate logic on every login page
```

### Why This Decision

**DRY (Don't Repeat Yourself)**: Logic in hook, not duplicated in components.

**Centralized**: Change token storage strategy once (hook), not everywhere.

**Consistency**: All components use same hook → same behavior.

**Testability**: Mock hook once, all components work.

### Hook Responsibility
```javascript
// useLogin() does:
- POST /auth/login/
- Extract tokens from response
- Store in localStorage
- Invalidate auth queries
- Return mutate function
```

### Alternative Considered: Manual Token Storage
```javascript
const handleLogin = async () => {
  const response = await apiClient.post('/auth/login/', { username, password })
  localStorage.setItem('access_token', response.access)
}
```

**Why Not**: Couples component to storage details. Hard to change later.

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Client-side validation** | Instant feedback, fewer API calls | May not catch all edge cases (backend validates) |
| **Inline styles** | Encapsulation, no CSS conflicts | Larger component file |
| **Controlled inputs** | React best practice, realtime validation | More state management |
| **Touched field tracking** | Better UX, progressive disclosure | Extra state tracking |
| **Disable button during loading** | Prevent duplicates, show feedback | User can't retry on network failure (can press again after) |
| **Replace history on login** | Cleaner browser back button | Can't use back to go to login (good for security) |
| **NavBar only in authenticated zone** | Simpler component, cleaner routing | Two separate routing structures |
| **Show demo credentials** | Developer convenience | Security: remove in production |
| **getErrorMessage() utility** | Consistency, user-friendly | Extra utility function |
| **Hook handles token storage** | DRY, testability | Component doesn't see storage (opaque) |

---

## Complete User Flow

```
1. User visits app
   → ProtectedRoute checks for token
   → No token → Redirect to /login

2. User at /login
   → See LoginPage with username/password form
   → See demo credentials

3. User enters username (e.g., "alice")
   → Form validates: username present ✓

4. User enters password
   → Form validates: password present ✓

5. User clicks "Login"
   → Button disabled, shows "Logging in..."
   → useLogin() hook sends POST /auth/login/

6a. Success
   → Backend returns {access_token, refresh_token}
   → useLogin() stores tokens in localStorage
   → Component redirects to /dashboard (replace history)
   → ProtectedRoute checks token → Present → Allows access
   → NavBar renders with username

6b. Failure (invalid credentials)
   → Backend returns 401
   → getErrorMessage() formats: "Unauthorized. Please log in."
   → LoginPage displays error alert
   → Button re-enabled, user can retry

7. User logged in
   → Token attached to all requests via apiClient interceptor
   → After 1 hour, token expires
   → Next request → 401
   → Interceptor refreshes token automatically
   → Request retried with new token
   → User sees no interruption

8. User clicks "Logout"
   → NavBar logout button → useLogout()
   → useLogout() clears localStorage
   → useLogout() redirects to /login
   → Loop back to step 1
```

---

Chunk 3.2 completes the authentication flow. Users can now log in, stay logged in, and log out. Next chunks add functionality (upload, review, export) on top of this foundation.

