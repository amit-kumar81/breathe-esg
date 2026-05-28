/**
 * Authentication Hook
 *
 * Manages login, logout, and current user state.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

/**
 * Get current logged-in user profile
 */
export function useCurrentUser() {
  return useQuery({
    queryKey: ['auth', 'currentUser'],
    queryFn: async () => {
      const response = await apiClient.get('/auth/me/')
      return response.data
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 1,
    enabled: !!localStorage.getItem('access_token')
  })
}

/**
 * Login mutation
 */
export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (credentials) => {
      const response = await apiClient.post('/auth/login/', credentials)
      const { access, refresh } = response.data

      // Store tokens
      localStorage.setItem('access_token', access)
      localStorage.setItem('refresh_token', refresh)

      return response.data
    },
    onSuccess: () => {
      // Refetch current user
      queryClient.invalidateQueries({ queryKey: ['auth', 'currentUser'] })
    }
  })
}

/**
 * Logout mutation
 */
export function useLogout() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      // Call logout endpoint (optional in JWT, but good for audit trail)
      try {
        await apiClient.post('/auth/logout/')
      } catch {
        // ignore — tokens are cleared regardless
      }
    },
    onSuccess: () => {
      // Clear tokens
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')

      // Clear all queries
      queryClient.clear()

      // Redirect to login
      window.location.href = '/login'
    }
  })
}

/**
 * Check if user is authenticated
 */
export function useIsAuthenticated() {
  return !!localStorage.getItem('access_token')
}
