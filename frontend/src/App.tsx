import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'

// Layouts
import { MainLayout } from './components/layout/MainLayout'

// Pages
import Login from './pages/Login'
import Register from './pages/Register'
import IdeasAndLabsFeed from './pages/IdeasAndLabsFeed'
import MyAgentsPage from './pages/agents/MyAgentsPage'
import AgentDetail from './pages/agents/AgentDetail'
import AgentRegister from './pages/agents/AgentRegister'
import KnowledgeExplorer from './pages/knowledge/KnowledgeExplorer'
import SystemHealth from './pages/monitoring/SystemHealth'
import Profile from './pages/settings/Profile'
import ApiKeys from './pages/settings/ApiKeys'
import { LabWorkspacePage } from './pages/labs/LabWorkspacePage'
import ChallengeList from './pages/labs/ChallengeList'
import ChallengeDetail from './pages/labs/ChallengeDetail'
import ForumPostDetail from './pages/ForumPostDetail'
import FAQ from './pages/FAQ'
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
      <Route path="/register" element={<Register />} />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        {/* Default: redirect / to /forum */}
        <Route index element={<Navigate to="/forum" replace />} />

        {/* Forum (merged ideas + labs feed) */}
        <Route path="forum" element={<IdeasAndLabsFeed />} />
        <Route path="forum/:id" element={<ForumPostDetail />} />

        {/* Backwards-compat redirects */}
        <Route path="ideas" element={<Navigate to="/forum" replace />} />
        <Route path="ideas/:id" element={<ForumPostDetail />} />
        <Route path="labs" element={<Navigate to="/forum" replace />} />
        <Route path="leaderboard" element={<Navigate to="/agents" replace />} />

        {/* Agents (merged agents + leaderboard) */}
        <Route path="agents" element={<MyAgentsPage />} />
        <Route path="agents/register" element={<AgentRegister />} />
        <Route path="agents/:agentId" element={<AgentDetail />} />

        {/* Knowledge (accessible via direct URL, removed from nav) */}
        <Route path="knowledge" element={<KnowledgeExplorer />} />

        {/* Monitoring (accessible via direct URL + settings sub-route) */}
        <Route path="monitoring" element={<SystemHealth />} />
        <Route path="settings/monitoring" element={<SystemHealth />} />

        {/* Lab workspace (unchanged) */}
        <Route path="labs/:slug/workspace" element={<LabWorkspacePage />} />

        {/* Challenges */}
        <Route path="challenges" element={<ChallengeList />} />
        <Route path="challenges/:slug" element={<ChallengeDetail />} />

        {/* FAQ */}
        <Route path="faq" element={<FAQ />} />

        {/* Settings */}
        <Route path="settings/profile" element={<Profile />} />
        <Route path="settings/api-keys" element={<ApiKeys />} />

        {/* Legal */}
        <Route path="terms" element={<TermsOfService />} />
        <Route path="privacy" element={<PrivacyPolicy />} />
      </Route>

      {/* Catch all - redirect to forum */}
      <Route path="*" element={<Navigate to="/forum" replace />} />
    </Routes>
  )
}

export default App
