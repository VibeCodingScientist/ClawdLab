import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'

// Layouts
import { MainLayout } from './components/layout/MainLayout'

// Pages
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import AgentList from './pages/agents/AgentList'
import AgentDetail from './pages/agents/AgentDetail'
import ExperimentList from './pages/experiments/ExperimentList'
import ExperimentDesigner from './pages/experiments/ExperimentDesigner'
import KnowledgeExplorer from './pages/knowledge/KnowledgeExplorer'
import SystemHealth from './pages/monitoring/SystemHealth'
import Profile from './pages/settings/Profile'
import ApiKeys from './pages/settings/ApiKeys'

// Protected Route Component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />

        {/* Agents */}
        <Route path="agents" element={<AgentList />} />
        <Route path="agents/:agentId" element={<AgentDetail />} />

        {/* Experiments */}
        <Route path="experiments" element={<ExperimentList />} />
        <Route path="experiments/new" element={<ExperimentDesigner />} />
        <Route path="experiments/:experimentId" element={<ExperimentDesigner />} />

        {/* Knowledge */}
        <Route path="knowledge" element={<KnowledgeExplorer />} />

        {/* Monitoring */}
        <Route path="monitoring" element={<SystemHealth />} />

        {/* Settings */}
        <Route path="settings/profile" element={<Profile />} />
        <Route path="settings/api-keys" element={<ApiKeys />} />
      </Route>

      {/* Catch all - redirect to dashboard */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
