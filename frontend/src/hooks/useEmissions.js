/**
 * Emissions Data Hooks
 *
 * Handles fetching and filtering emissions data.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

/**
 * Fetch paginated emissions records
 *
 * @param {Object} options - Query options
 * @param {number} options.page - Page number (1-indexed)
 * @param {string} options.statusFilter - Filter by review_status (APPROVED, PENDING, REJECTED)
 * @param {number} options.yearFilter - Filter by reporting year
 */
export function useEmissions(options = {}) {
  const { page = 1, statusFilter, yearFilter } = options

  return useQuery({
    queryKey: ['emissions', { page, statusFilter, yearFilter }],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', page)
      if (statusFilter) params.append('review_status', statusFilter)
      if (yearFilter) params.append('reporting_year', yearFilter)

      const response = await apiClient.get(`/emissions/?${params.toString()}`)
      return response.data
    },
    staleTime: 1000 * 60 // 1 minute
  })
}

/**
 * Fetch emissions summary/dashboard metrics
 *
 * @param {Object} filters - { year, facility, scope } — 'all' means no filter
 */
export function useEmissionsSummary(filters = {}) {
  return useQuery({
    queryKey: ['emissions', 'summary', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.year && filters.year !== 'all') params.append('year', filters.year)
      if (filters.facility && filters.facility !== 'all') params.append('facility_name', filters.facility)
      if (filters.scope && filters.scope !== 'all') params.append('scope', filters.scope.toUpperCase())

      const response = await apiClient.get(`/emissions/summary/?${params.toString()}`)
      return response.data
    },
    staleTime: 0
  })
}

/**
 * Export emissions data (CSV or JSON)
 *
 * @param {string} format - 'csv' or 'json'
 * @param {Object} filters - Optional filters (year, status)
 */
export function useEmissionsExport(format = 'json', filters = {}) {
  return useQuery({
    queryKey: ['emissions', 'export', format, filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('format', format)
      if (filters.year) params.append('year', filters.year)
      if (filters.status) params.append('status', filters.status)

      const response = await apiClient.get(
        `/emissions/export/?${params.toString()}`,
        {
          responseType: format === 'csv' ? 'blob' : 'json'
        }
      )

      if (format === 'csv') {
        // Return blob for CSV download
        return response.data
      }

      // Return parsed JSON
      return response.data
    },
    enabled: false // Don't fetch automatically
  })
}
