/**
 * Main application layout with sidebar navigation
 */

import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { Footer } from './Footer'
import { ActivityTicker } from '../common/ActivityTicker'
import { ErrorBoundary } from '../common/ErrorBoundary'

export function MainLayout() {
  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <Sidebar />

      {/* Main content area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <Header />

        {/* Activity ticker */}
        <ActivityTicker />

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>

        {/* Footer */}
        <Footer />
      </div>
    </div>
  )
}
