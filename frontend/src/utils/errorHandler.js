/**
 * Error Handler Utilities
 *
 * Extracts and formats API error messages.
 */

/**
 * Extract error message from API response
 *
 * @param {Error} error - Axios error object
 * @returns {string} - Formatted error message
 */
export function getErrorMessage(error) {
  if (!error) return 'An unknown error occurred'

  // Network error
  if (!error.response) {
    return error.message || 'Network error. Please check your connection.'
  }

  const { data, status } = error.response

  // Handle DRF error responses
  if (data.detail) {
    return data.detail
  }

  // Handle field-level errors
  if (typeof data === 'object' && !Array.isArray(data)) {
    const errors = Object.entries(data)
      .map(([field, messages]) => {
        const msg = Array.isArray(messages) ? messages[0] : messages
        return `${field}: ${msg}`
      })
      .join(', ')
    if (errors) return errors
  }

  // HTTP status messages
  const statusMessages = {
    400: 'Bad request. Please check your input.',
    401: 'Unauthorized. Please log in.',
    403: 'You do not have permission to perform this action.',
    404: 'Resource not found.',
    500: 'Server error. Please try again later.',
    502: 'Bad gateway. The server may be temporarily unavailable.',
    503: 'Service unavailable. Please try again later.'
  }

  return statusMessages[status] || `Error ${status}: An error occurred`
}

/**
 * Format error for display to user
 *
 * @param {Error} error - Error object
 * @returns {Object} - { title, message }
 */
export function formatError(error) {
  const message = getErrorMessage(error)

  return {
    title: 'Error',
    message
  }
}

/**
 * Log error to console and optionally send to error tracking
 *
 * @param {Error} error - Error object
 * @param {string} context - Where error occurred
 */
export function logError(error, context) {
  console.error(`[${context}]`, error)

  // TODO: Send to error tracking service (Sentry, etc.)
}
