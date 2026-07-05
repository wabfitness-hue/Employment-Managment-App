import { useEffect, Component } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { useAuthStore } from './store/auth'
import { getMe } from './api/auth'

import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { SetupPage } from './pages/SetupPage'
import { DashboardPage } from './pages/DashboardPage'
import { PeopleListPage } from './pages/PeopleListPage'
import { PersonDetailPage } from './pages/PersonDetailPage'
import { PersonFormPage } from './pages/PersonFormPage'
import { ContractsPage } from './pages/ContractsPage'
import { CardsPage } from './pages/CardsPage'
import { ImportPage } from './pages/ImportPage'
import { SettingsPage } from './pages/SettingsPage'
import { AccessPage } from './pages/AccessPage'

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Uncaught render error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center space-y-4 p-8">
            <h1 className="text-2xl font-bold text-gray-900">Something went wrong</h1>
            <p className="text-gray-500">An unexpected error occurred. Please refresh the page.</p>
            <button
              onClick={() => window.location.href = '/dashboard'}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Go to dashboard
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuthStore()
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  return user ? <>{children}</> : <Navigate to="/login" replace />
}

function AppInit() {
  const { setUser, setLoading } = useAuthStore()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }
    getMe()
      .then(u => { setUser(u); setLoading(false) })
      .catch(() => { localStorage.clear(); setLoading(false) })
  }, [setUser, setLoading])

  return null
}

export default function App() {
  return (
    <ErrorBoundary>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AppInit />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/setup" element={<SetupPage />} />

          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/people" element={<PeopleListPage />} />
            <Route path="/people/new" element={<PersonFormPage />} />
            <Route path="/people/:id" element={<PersonDetailPage />} />
            <Route path="/people/:id/edit" element={<PersonFormPage />} />
            <Route path="/contracts" element={<ContractsPage />} />
            <Route path="/cards" element={<CardsPage />} />
            <Route path="/import" element={<ImportPage />} />
            <Route path="/access" element={<AccessPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/outlook" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
    </ErrorBoundary>
  )
}
