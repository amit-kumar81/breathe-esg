/**
 * Review Tasks Hooks
 *
 * Handles fetching and updating review tasks for analysts.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'

/**
 * Fetch paginated review tasks
 *
 * @param {Object} options - Query options
 * @param {number} options.page - Page number (1-indexed)
 * @param {string} options.status - Filter by task status (PENDING, APPROVED, REJECTED)
 * @param {string} options.priority - Filter by priority (HIGH, MEDIUM, LOW)
 */
export function useReviewTasks(options = {}) {
  const { page = 1, status, priority } = options

  return useQuery({
    queryKey: ['reviewTasks', { page, status, priority }],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('page', page)
      if (status) params.append('status', status)
      if (priority) params.append('priority', priority)

      const response = await apiClient.get(`/review/?${params.toString()}`)
      return response.data
    },
    staleTime: 1000 * 30 // 30 seconds
  })
}

/**
 * Fetch single review task detail
 *
 * @param {string} taskId - UUID of review task
 */
export function useReviewTaskDetail(taskId) {
  return useQuery({
    queryKey: ['reviewTasks', taskId],
    queryFn: async () => {
      const response = await apiClient.get(`/review/${taskId}/`)
      return response.data
    },
    staleTime: 1000 * 30,
    enabled: !!taskId
  })
}

/**
 * Approve review task mutation
 *
 * @param {string} taskId - UUID of task to approve
 */
export function useApproveTask(taskId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (notes) => {
      const response = await apiClient.post(`/review/${taskId}/approve/`, {
        notes: notes || ''
      })
      return response.data
    },
    onSuccess: () => {
      // Invalidate review tasks and emissions
      queryClient.invalidateQueries({ queryKey: ['reviewTasks'] })
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
    }
  })
}

/**
 * Reject review task mutation
 *
 * @param {string} taskId - UUID of task to reject
 */
export function useRejectTask(taskId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (rejectionReason) => {
      const response = await apiClient.post(`/review/${taskId}/reject/`, {
        rejection_reason: rejectionReason
      })
      return response.data
    },
    onSuccess: () => {
      // Invalidate review tasks
      queryClient.invalidateQueries({ queryKey: ['reviewTasks'] })
    }
  })
}

/**
 * Request revision mutation
 *
 * @param {string} taskId - UUID of task to request revision
 */
export function useRequestRevision(taskId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (revisionNotes) => {
      const response = await apiClient.post(`/review/${taskId}/request-revision/`, {
        notes: revisionNotes
      })
      return response.data
    },
    onSuccess: () => {
      // Invalidate review tasks
      queryClient.invalidateQueries({ queryKey: ['reviewTasks'] })
    }
  })
}

/**
 * Get review summary/dashboard metrics
 */
export function useReviewSummary() {
  return useQuery({
    queryKey: ['review', 'summary'],
    queryFn: async () => {
      const response = await apiClient.get('/review/summary/')
      return response.data
    },
    staleTime: 1000 * 60 // 1 minute
  })
}
