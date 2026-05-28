/**
 * Ingestion Workflow Hooks
 *
 * Handles CSV upload, parsing, normalization workflow.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

/**
 * Fetch available data sources for the current tenant
 */
export function useDataSources() {
  return useQuery({
    queryKey: ['datasources'],
    queryFn: async () => {
      const response = await apiClient.get('/ingest/datasources/')
      return response.data
    },
    staleTime: 1000 * 60 * 5
  })
}

/**
 * Fetch paginated ingestions
 *
 * @param {Object} options - Query options
 * @param {number} options.page - Page number (1-indexed)
 * @param {string} options.step - Filter by current step (UPLOADED, PARSED, NORMALIZED)
 */
export function useIngestions(options = {}) {
  const { page = 1, step } = options

  return useQuery({
    queryKey: ['ingestions', { page, step }],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', page)
      if (step) params.append('step', step)

      const response = await apiClient.get(`/ingest/?${params.toString()}`)
      return response.data
    },
    staleTime: 1000 * 30,
    retry: false
  })
}

/**
 * Fetch single ingestion detail with samples
 *
 * @param {string} ingestionId - UUID of ingestion
 */
export function useIngestionDetail(ingestionId) {
  return useQuery({
    queryKey: ['ingestions', ingestionId],
    queryFn: async () => {
      const response = await apiClient.get(`/ingest/${ingestionId}/`)
      return response.data
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    enabled: !!ingestionId
  })
}

/**
 * Upload CSV file mutation
 */
export function useUploadCSV() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ file, dataSourceId }) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('data_source_id', dataSourceId)

      // Setting Content-Type to undefined removes the instance-level
      // 'application/json' default, letting axios auto-set multipart/form-data
      // with the correct boundary for FormData.
      const response = await apiClient.post('/ingest/upload/', formData, {
        headers: { 'Content-Type': undefined }
      })

      return response.data
    },
    onSuccess: () => {
      // Refetch ingestions list
      queryClient.invalidateQueries({ queryKey: ['ingestions'] })
    }
  })
}

/**
 * Parse CSV mutation
 *
 * @param {string} ingestionId - UUID of ingestion to parse
 */
export function useParse(ingestionId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post(`/ingest/${ingestionId}/parse/`)
      return response.data
    },
    onSuccess: () => {
      // Invalidate both list and detail queries
      queryClient.invalidateQueries({ queryKey: ['ingestions'] })
      queryClient.invalidateQueries({ queryKey: ['ingestions', ingestionId] })
    }
  })
}

/**
 * Normalize records mutation
 *
 * @param {string} ingestionId - UUID of ingestion to normalize
 */
export function useNormalize(ingestionId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post(`/ingest/${ingestionId}/normalize/`)
      return response.data
    },
    onSuccess: () => {
      // Remove the cached entry so React Query must fetch fresh data
      // (refetchQueries alone can serve stale cache in some v5 edge cases)
      queryClient.removeQueries({ queryKey: ['ingestions', ingestionId], exact: true })
      queryClient.invalidateQueries({ queryKey: ['ingestions'] })
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
    }
  })
}

/**
 * Get ingestion status/progress
 *
 * @param {string} ingestionId - UUID of ingestion
 */
export function useIngestionStatus(ingestionId) {
  return useQuery({
    queryKey: ['ingestions', ingestionId, 'status'],
    queryFn: async () => {
      const response = await apiClient.get(`/ingest/${ingestionId}/status/`)
      return response.data
    },
    staleTime: 1000 * 10, // 10 seconds
    enabled: !!ingestionId
  })
}
