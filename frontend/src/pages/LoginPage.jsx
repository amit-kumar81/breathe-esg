import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLogin } from '../hooks/useAuth'
import { getErrorMessage } from '../utils/errorHandler'

function LoginPage() {
  const navigate = useNavigate()
  const { mutate: login, isPending, error } = useLogin()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState({})

  const handleSubmit = (e) => {
    e.preventDefault()

    if (!username || !password) {
      setTouched({ username: true, password: true })
      return
    }

    login(
      { username, password },
      {
        onSuccess: () => {
          // Navigate to dashboard on success
          navigate('/dashboard', { replace: true })
        }
      }
    )
  }

  const handleBlur = (field) => {
    setTouched((prev) => ({ ...prev, [field]: true }))
  }

  const hasError = (field) => {
    const values = { username, password }
    return touched[field] && !values[field]
  }

  const errorMessage = error ? getErrorMessage(error) : null

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.header}>
          <h1 style={styles.title}>Breathe ESG</h1>
          <p style={styles.subtitle}>Emissions Data Management</p>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* Error Alert */}
          {errorMessage && (
            <div style={styles.alert}>
              <strong>Login Failed</strong>
              <p>{errorMessage}</p>
            </div>
          )}

          {/* Username Field */}
          <div style={styles.formGroup}>
            <label htmlFor="username" style={styles.label}>
              Username
            </label>
            <input
              id="username"
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onBlur={() => handleBlur('username')}
              disabled={isPending}
              style={{
                ...styles.input,
                borderColor: hasError('username') ? '#dc3545' : undefined
              }}
            />
            {hasError('username') && (
              <p style={styles.errorText}>Username is required</p>
            )}
          </div>

          {/* Password Field */}
          <div style={styles.formGroup}>
            <label htmlFor="password" style={styles.label}>
              Password
            </label>
            <input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => handleBlur('password')}
              disabled={isPending}
              style={{
                ...styles.input,
                borderColor: hasError('password') ? '#dc3545' : undefined
              }}
            />
            {hasError('password') && (
              <p style={styles.errorText}>Password is required</p>
            )}
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isPending}
            style={{
              ...styles.button,
              opacity: isPending ? 0.6 : 1,
              cursor: isPending ? 'not-allowed' : 'pointer'
            }}
          >
            {isPending ? (
              <>
                <span style={styles.spinner}></span>
                Logging in...
              </>
            ) : (
              'Login'
            )}
          </button>
        </form>

        {/* Demo Credentials Info */}
        <div style={styles.info}>
          <p style={styles.infoText}>
            <strong>Demo Credentials:</strong>
            <br />
            Username: <code>alice</code> or <code>bob</code>
            <br />
            Password: <code>password123</code>
          </p>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    padding: '20px'
  },
  card: {
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    padding: '40px',
    width: '100%',
    maxWidth: '400px'
  },
  header: {
    textAlign: 'center',
    marginBottom: '40px'
  },
  title: {
    margin: '0 0 10px 0',
    fontSize: '28px',
    color: '#333',
    fontWeight: 'bold'
  },
  subtitle: {
    margin: '0',
    fontSize: '14px',
    color: '#666'
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px'
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  label: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#333'
  },
  input: {
    padding: '12px',
    fontSize: '14px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontFamily: 'inherit',
    transition: 'border-color 0.2s'
  },
  errorText: {
    margin: '0',
    fontSize: '12px',
    color: '#dc3545'
  },
  button: {
    padding: '12px',
    fontSize: '16px',
    fontWeight: '500',
    color: 'white',
    backgroundColor: '#007bff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px'
  },
  spinner: {
    display: 'inline-block',
    width: '14px',
    height: '14px',
    border: '2px solid rgba(255, 255, 255, 0.3)',
    borderTop: '2px solid white',
    borderRadius: '50%',
    animation: 'spin 0.6s linear infinite'
  },
  alert: {
    padding: '12px',
    backgroundColor: '#f8d7da',
    border: '1px solid #f5c6cb',
    borderRadius: '4px',
    color: '#721c24',
    fontSize: '14px'
  },
  info: {
    marginTop: '30px',
    padding: '15px',
    backgroundColor: '#e7f3ff',
    border: '1px solid #b3d9ff',
    borderRadius: '4px'
  },
  infoText: {
    margin: '0',
    fontSize: '12px',
    color: '#004085',
    lineHeight: '1.6'
  }
}

export default LoginPage
