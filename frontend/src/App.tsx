import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'

// Layouts
import { MainLayout } from './components/layout/MainLayout'

// Pages
import LandingPage from './pages/LandingPage'
import Login from './pages/Login'
import AgentList from './pages/agents/AgentList'
import AgentDetail from './pages/agents/AgentDetail'
import ExperimentList from './pages/experiments/ExperimentList'
import ExperimentDesigner from './pages/experiments/ExperimentDesigner'
import KnowledgeExplorer from './pages/knowledge/KnowledgeExplorer'
import SystemHealth from './pages/monitoring/SystemHealth'
import Profile from './pages/settings/Profile'
import ApiKeys from './pages/settings/ApiKeys'
import { LabWorkspacePage } from './pages/labs/LabWorkspacePage'
import LabListPage from './pages/labs/LabListPage'
import ChallengeList from './pages/labs/ChallengeList'
import ChallengeDetail from './pages/labs/ChallengeDetail'
import { ObservatoryPage } from './pages/observatory/ObservatoryPage'
import Leaderboard from './pages/agents/Leaderboard'
import TermsOfService from './pages/legal/TermsOfService'
import PrivacyPolicy from './pages/legal/PrivacyPolicy'

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
        <Route index element={<LandingPage />} />

        {/* Agents */}
        <Route path="agents" element={<AgentList />} />
        <Route path="agents/:agentId" element={<AgentDetail />} />

        {/* Experiments */}
        <Route path="experiments" element={<ExperimentList />} />
        <Route path="experiments/new" element={<ExperimentDesigner />} />
        <Route path="experiments/:experimentId" element={<ExperimentDesigner />} />

        {/* Knowledge (accessible via direct URL, removed from nav) */}
        <Route path="knowledge" element={<KnowledgeExplorer />} />

        {/* Monitoring (accessible via direct URL + settings sub-route) */}
        <Route path="monitoring" element={<SystemHealth />} />
        <Route path="settings/monitoring" element={<SystemHealth />} />

        {/* Labs */}
        <Route path="labs" element={<LabListPage />} />
        <Route path="labs/:slug/workspace" element={<LabWorkspacePage />} />

        {/* Challenges */}
        <Route path="challenges" element={<ChallengeList />} />
        <Route path="challenges/:slug" element={<ChallengeDetail />} />

        {/* Leaderboard */}
        <Route path="leaderboard" element={<Leaderboard />} />

        {/* Observatory (accessible via direct URL, removed from nav) */}
        <Route path="observatory" element={<ObservatoryPage />} />

        {/* Settings */}
        <Route path="settings/profile" element={<Profile />} />
        <Route path="settings/api-keys" element={<ApiKeys />} />

        {/* Legal */}
        <Route path="terms" element={<TermsOfService />} />
        <Route path="privacy" element={<PrivacyPolicy />} />
      </Route>

      {/* Catch all - redirect to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
