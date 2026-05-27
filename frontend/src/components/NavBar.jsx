/**
 * Navigation Bar Component
 *
 * Displays app header with user info and logout button.
 * Only shown when user is authenticated.
 */

import { useNavigate } from 'react-router-dom'
import { useCurrentUser, useLogout } from '../hooks/useAuth'

function NavBar() {
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const { mutate: logout } = useLogout()

  const handleLogout = () => {
    logout()
  }

  return (
    <nav style={styles.navbar}>
      <div style={styles.container}>
        {/* Logo/Title */}
        <div style={styles.left}>
          <h1 style={styles.title}>Breathe ESG</h1>
        </div>

        {/* User Info and Actions */}
        <div style={styles.right}>
          {user && (
            <>
              <div style={styles.userInfo}>
                <span style={styles.username}>{user.username}</span>
                <span style={styles.tenant}>({user.tenant_name})</span>
              </div>
              <button
                onClick={handleLogout}
                style={styles.logoutButton}
                onMouseOver={(e) => {
                  e.target.style.backgroundColor = '#c82333'
                }}
                onMouseOut={(e) => {
                  e.target.style.backgroundColor = '#dc3545'
                }}
              >
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}

const styles = {
  navbar: {
    backgroundColor: '#333',
    padding: '0',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
  },
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '12px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  left: {
    display: 'flex',
    alignItems: 'center'
  },
  title: {
    margin: '0',
    fontSize: '20px',
    fontWeight: 'bold',
    color: '#fff'
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px'
  },
  userInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
    color: '#fff'
  },
  username: {
    fontWeight: '500'
  },
  tenant: {
    color: '#bbb',
    fontSize: '12px'
  },
  logoutButton: {
    padding: '8px 16px',
    backgroundColor: '#dc3545',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'background-color 0.2s'
  }
}

export default NavBar
