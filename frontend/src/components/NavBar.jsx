import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useCurrentUser, useLogout } from '../hooks/useAuth'

function NavBar() {
  const { data: user } = useCurrentUser()
  const { mutate: logout } = useLogout()
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = () => setMenuOpen(false)

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <span className="navbar-brand">Breathe ESG</span>

        {/* Desktop nav links */}
        <nav className="navbar-links">
          <NavLink to="/dashboard" style={linkStyle} onClick={closeMenu}>Dashboard</NavLink>
          <NavLink to="/upload"    style={linkStyle} onClick={closeMenu}>Upload</NavLink>
          <NavLink to="/review"    style={linkStyle} onClick={closeMenu}>Review</NavLink>
        </nav>

        {/* Desktop user info */}
        <div className="navbar-right">
          {user && (
            <>
              <span className="navbar-username">
                {user.username}
                {user.tenant_name && <span style={{ color: '#888', fontSize: '12px', marginLeft: 6 }}>({user.tenant_name})</span>}
              </span>
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
            {user.tenant_name && ` · ${user.tenant_name}`}
          </div>
        )}
        <NavLink to="/dashboard" style={drawerLinkStyle} onClick={closeMenu}>Dashboard</NavLink>
        <NavLink to="/upload"    style={drawerLinkStyle} onClick={closeMenu}>Upload</NavLink>
        <NavLink to="/review"    style={drawerLinkStyle} onClick={closeMenu}>Review</NavLink>
        {user && (
          <button className="drawer-logout" onClick={() => { logout(); closeMenu() }}>Logout</button>
        )}
      </div>
    </header>
  )
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
