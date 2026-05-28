import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useCurrentUser, useLogout } from '../hooks/useAuth'

function NavBar() {
  const { data: user } = useCurrentUser()
  const { mutate: logout } = useLogout()
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = () => setMenuOpen(false)

  const role = user?.role
  const canUpload = role === 'ADMIN' || role === 'DATA_PROVIDER'
  const canReview = role === 'ADMIN' || role === 'ANALYST'

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <span className="navbar-brand">Breathe ESG</span>

        {/* Desktop nav links */}
        <nav className="navbar-links">
          <NavLink to="/dashboard" style={linkStyle} onClick={closeMenu}>Dashboard</NavLink>
          {canUpload && <NavLink to="/upload" style={linkStyle} onClick={closeMenu}>Upload</NavLink>}
          {canReview && <NavLink to="/review" style={linkStyle} onClick={closeMenu}>Review</NavLink>}
        </nav>

        {/* Desktop user info */}
        <div className="navbar-right">
          {user && (
            <>
              <span className="navbar-username">
                {user.username}
                {user.tenant?.name && <span style={{ color: '#888', fontSize: '12px', marginLeft: 6 }}>({user.tenant.name})</span>}
              </span>
              <span style={roleBadgeStyle(user.role)}>{user.role}</span>
              <button className="navbar-logout" onClick={() => logout()}>Logout</button>
            </>
          )}
        </div>

        {/* Hamburger — mobile only */}
        <button
          className="navbar-hamburger"
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle menu"
        >
          {menuOpen ? '✕' : '☰'}
        </button>
      </div>

      {/* Mobile drawer */}
      <div className={`navbar-drawer ${menuOpen ? 'open' : ''}`}>
        {user && (
          <div className="drawer-user">
            Signed in as <strong>{user.username}</strong>
            {user.tenant?.name && ` · ${user.tenant.name}`}
            {user.role && <span style={{ ...roleBadgeStyle(user.role), marginLeft: 8, fontSize: '11px' }}>{user.role}</span>}
          </div>
        )}
        <NavLink to="/dashboard" style={drawerLinkStyle} onClick={closeMenu}>Dashboard</NavLink>
        {canUpload && <NavLink to="/upload" style={drawerLinkStyle} onClick={closeMenu}>Upload</NavLink>}
        {canReview && <NavLink to="/review" style={drawerLinkStyle} onClick={closeMenu}>Review</NavLink>}
        {user && (
          <button className="drawer-logout" onClick={() => { logout(); closeMenu() }}>Logout</button>
        )}
      </div>
    </header>
  )
}

const roleBadgeStyle = (role) => {
  const colors = {
    ADMIN: { background: '#dc3545', color: '#fff' },
    ANALYST: { background: '#007bff', color: '#fff' },
    DATA_PROVIDER: { background: '#fd7e14', color: '#fff' },
    VIEWER: { background: '#6c757d', color: '#fff' },
  }
  const c = colors[role] || colors.VIEWER
  return {
    fontSize: '11px',
    fontWeight: '600',
    padding: '2px 7px',
    borderRadius: '10px',
    background: c.background,
    color: c.color,
    letterSpacing: '0.3px',
    whiteSpace: 'nowrap',
  }
}

const linkStyle = ({ isActive }) => ({
  color: isActive ? '#fff' : '#bbb',
  textDecoration: 'none',
  fontSize: '14px',
  fontWeight: isActive ? '600' : '400',
  padding: '4px 10px',
  borderRadius: '4px',
  backgroundColor: isActive ? 'rgba(255,255,255,0.15)' : 'transparent',
  whiteSpace: 'nowrap'
})

const drawerLinkStyle = ({ isActive }) => ({
  color: isActive ? '#fff' : '#bbb',
  textDecoration: 'none',
  fontSize: '15px',
  fontWeight: isActive ? '600' : '400',
  padding: '10px 0',
  display: 'block',
  borderBottom: '1px solid #3a3a3a'
})

export default NavBar
