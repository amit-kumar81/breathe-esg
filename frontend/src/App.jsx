import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import ErrorBoundary from './components/ErrorBoundary'
import ProtectedRoute from './components/ProtectedRoute'
import RequireRole from './components/RequireRole'
import NavBar from './components/NavBar'

import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UploadPage from './pages/UploadPage'
import IngestionReviewPage from './pages/IngestionReviewPage'
import ReviewPage from './pages/ReviewPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60
    },
    mutations: {
      retry: 1
    }
  }
})

const UPLOAD_ROLES = ['ADMIN', 'DATA_PROVIDER']
const REVIEW_ROLES = ['ADMIN', 'ANALYST']

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <Router>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <>
                    <NavBar />
                    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
                      <Routes>
                        <Route path="/dashboard" element={<DashboardPage />} />

                        <Route path="/upload" element={
                          <RequireRole allowedRoles={UPLOAD_ROLES}>
                            <UploadPage />
                          </RequireRole>
                        } />

                        <Route path="/ingest/:id" element={
                          <RequireRole allowedRoles={UPLOAD_ROLES}>
                            <IngestionReviewPage />
                          </RequireRole>
                        } />

                        <Route path="/review" element={
                          <RequireRole allowedRoles={REVIEW_ROLES}>
                            <ReviewPage />
                          </RequireRole>
                        } />

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
