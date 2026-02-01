/**
 * HealthDashboard -- Displays agent health status with three-probe indicators
 * (liveness, readiness, progress), warnings, and an action recommendation badge.
 * Auto-refreshes every 30 seconds.
 */

import { useEffect, useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'

// ===========================================
// TYPES
// ===========================================

interface HealthAssessment {
  agent_id: string
  operational_state: string
  research_state: string
  liveness_ok: boolean
  readiness_ok: boolean
  progress_ok: boolean
  warnings: string[]
  recommendation: string
}

// ===========================================
// CONSTANTS
// ===========================================

const REFRESH_INTERVAL_MS = 30_000

type ProbeStatus = 'ok' | 'warning' | 'error'

const PROBE_DOT_COLORS: Record<ProbeStatus, string> = {
  ok: 'bg-green-500',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
}

const PROBE_DOT_RING_COLORS: Record<ProbeStatus, string> = {
  ok: 'ring-green-500/20',
  warning: 'ring-yellow-500/20',
  error: 'ring-red-500/20',
}

const RECOMMENDATION_STYLES: Record<string, { bg: string; text: string }> = {
  continue: { bg: 'bg-green-100', text: 'text-green-800' },
  investigate: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
  restart: { bg: 'bg-orange-100', text: 'text-orange-800' },
  park: { bg: 'bg-red-100', text: 'text-red-800' },
}

function getRecommendationStyle(recommendation: string): { bg: string; text: string } {
  return RECOMMENDATION_STYLES[recommendation.toLowerCase()] ?? {
    bg: 'bg-gray-100',
    text: 'text-gray-800',
  }
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

function ProbeCard({
  label,
  status,
  description,
}: {
  label: string
  status: ProbeStatus
  description: string
}) {
  const dotColor = PROBE_DOT_COLORS[status]
  const ringColor = PROBE_DOT_RING_COLORS[status]
  const statusLabel = status === 'ok' ? 'OK' : status === 'warning' ? 'Warning' : 'Error'

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          {/* Status dot with ring */}
          <div className={`h-2 w-2 shrink-0 rounded-full ${dotColor} ring-4 ${ringColor}`} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{label}</p>
            <p className="text-xs text-muted-foreground truncate">{description}</p>
          </div>
          <span className="text-xs font-medium text-muted-foreground">{statusLabel}</span>
        </div>
      </CardContent>
    </Card>
  )
}

function WarningsList({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Warnings</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {warnings.map((warning, index) => (
            <li
              key={index}
              className="flex items-start gap-2 text-sm"
            >
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
              <span className="text-amber-700">{warning}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function RecommendationBadge({ recommendation }: { recommendation: string }) {
  const style = getRecommendationStyle(recommendation)
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold capitalize ${style.bg} ${style.text}`}
    >
      {recommendation.replace(/_/g, ' ')}
    </span>
  )
}

// ===========================================
// HELPERS
// ===========================================

function deriveLivenessStatus(ok: boolean): ProbeStatus {
  return ok ? 'ok' : 'error'
}

function deriveReadinessStatus(ok: boolean): ProbeStatus {
  return ok ? 'ok' : 'warning'
}

function deriveProgressStatus(ok: boolean): ProbeStatus {
  return ok ? 'ok' : 'warning'
}

// ===========================================
// MAIN COMPONENT
// ===========================================

interface HealthDashboardProps {
  agentId: string
}

export default function HealthDashboard({ agentId }: HealthDashboardProps) {
  const [health, setHealth] = useState<HealthAssessment | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchHealth = useCallback(async (isInitial: boolean) => {
    if (isInitial) {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await apiClient.get<HealthAssessment>(
        `/lifecycle/agents/${agentId}/health`
      )
      setHealth(response.data)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load health data'
      setError(message)
    } finally {
      if (isInitial) {
        setLoading(false)
      }
    }
  }, [agentId])

  useEffect(() => {
    let cancelled = false

    // Initial fetch
    fetchHealth(true)

    // Auto-refresh interval
    const intervalId = setInterval(() => {
      if (!cancelled) {
        fetchHealth(false)
      }
    }, REFRESH_INTERVAL_MS)

    return () => {
      cancelled = true
      clearInterval(intervalId)
    }
  }, [fetchHealth])

  // ------ Loading ------
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  // ------ Error ------
  if (error) {
    return (
      <div className="p-4">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    )
  }

  // ------ No data ------
  if (!health) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-muted-foreground">No health data available.</p>
      </div>
    )
  }

  const livenessStatus = deriveLivenessStatus(health.liveness_ok)
  const readinessStatus = deriveReadinessStatus(health.readiness_ok)
  const progressStatus = deriveProgressStatus(health.progress_ok)

  return (
    <div className="space-y-4">
      {/* Header with recommendation */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">Agent Health</h3>
        <RecommendationBadge recommendation={health.recommendation} />
      </div>

      {/* Three probe cards */}
      <div className="grid gap-3 sm:grid-cols-3">
        <ProbeCard
          label="Liveness"
          status={livenessStatus}
          description={health.operational_state.replace(/_/g, ' ')}
        />
        <ProbeCard
          label="Readiness"
          status={readinessStatus}
          description={health.readiness_ok ? 'Ready' : 'Not ready'}
        />
        <ProbeCard
          label="Progress"
          status={progressStatus}
          description={health.research_state.replace(/_/g, ' ')}
        />
      </div>

      {/* Warnings section */}
      <WarningsList warnings={health.warnings} />
    </div>
  )
}
