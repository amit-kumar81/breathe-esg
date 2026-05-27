/**
 * Main App Component
 *
 * Sets up routing, query client, and error boundaries.
 */

import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import ErrorBoundary from './components/ErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import NavBar from './components/NavBar'

// Pages
import LoginPage from './pages/LoginPage'
import UploadPage from './pages/UploadPage'
import IngestionReviewPage from './pages/IngestionReviewPage'

// Pages (will be created in Phase 3.4+)
// import DashboardPage from './pages/DashboardPage'
// import ReviewPage from './pages/ReviewPage'

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 // 1 minute
    },
    mutations: {
      retry: 1
    }
  }
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Router>
          <Routes>
            {/* Public route: Login */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes - require authentication */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <>
                    <NavBar />
                    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
                      <Routes>
                        <Route path="/upload" element={<UploadPage />} />
                        <Route path="/ingest/:id" element={<IngestionReviewPage />} />
                        <Route path="/dashboard" element={<div>Dashboard (Coming in 3.4)</div>} />
                        <Route path="/review" element={<div>Review (Coming in 3.4)</div>} />
                        <Route path="/emissions" element={<div>Emissions (Coming in 3.4)</div>} />

                        {/* Default redirect */}
                        <Route path="/" element={<Navigate to="/dashboard" replace />} />
                        <Route path="*" element={<Navigate to="/dashboard" replace />} />
                      </Routes>
                    </div>
                  </>
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </ErrorBoundary>
    </QueryClientProvider>
  )
}

export default App
