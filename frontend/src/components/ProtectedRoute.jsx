/**
 * Protected Route Component
 *
 * Ensures user is authenticated before accessing protected pages.
 */

import React from 'react'
import { Navigate } from 'react-router-dom'
import { useCurrentUser } from '../hooks/useAuth'

function ProtectedRoute({ children }) {
  const { data: user, isLoading, error } = useCurrentUser()
  const token = localStorage.getItem('access_token')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (isLoading) {
    return <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>
  }

  if (error) {
    // Token is invalid or expired
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return <Navigate to="/login" replace />
  }

  // User is authenticated
  return children
}

export default ProtectedRoute
