import { useCurrentUser } from '../hooks/useAuth'

function RequireRole({ allowedRoles, children }) {
  const { data: user, isLoading } = useCurrentUser()

  if (isLoading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>
  }

  if (!user || !allowedRoles.includes(user.role)) {
    return (
      <div style={styles.container}>
        <div style={styles.box}>
          <h2 style={styles.title}>Access Denied</h2>
          <p style={styles.message}>
            Your role <strong>{user?.role || 'unknown'}</strong> does not have permission to access this page.
          </p>
          <p style={styles.hint}>
            Required role: {allowedRoles.join(' or ')}
          </p>
        </div>
      </div>
    )
  }

  return children
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '60vh',
  },
  box: {
    textAlign: 'center',
    padding: '40px',
    backgroundColor: '#fff8f8',
    border: '1px solid #f5c6cb',
    borderRadius: '8px',
    maxWidth: '400px',
  },
  title: {
    color: '#721c24',
    margin: '0 0 12px 0',
  },
  message: {
    color: '#333',
    fontSize: '14px',
    margin: '0 0 8px 0',
  },
  hint: {
    color: '#888',
    fontSize: '12px',
    margin: '0',
  },
}

export default RequireRole
