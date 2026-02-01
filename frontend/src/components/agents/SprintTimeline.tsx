/**
 * SprintTimeline -- Displays a vertical timeline of an agent's sprint history,
 * showing goal, status, date range, outcome, and key stats for each sprint.
 */

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'

// ===========================================
// TYPES
// ===========================================

interface Sprint {
  id: string
  agent_id: string
  lab_id: string
  sprint_number: number
  goal: string
  approach: string | null
  started_at: string
  target_end_at: string
  actual_end_at: string | null
  status: string
  outcome_type: string | null
  outcome_summary: string | null
  claims_submitted: number
  findings_recorded: number
  reviews_completed: number
  hypotheses_active: number
  tokens_consumed: number
  checkpoints_created: number
  reviewed: boolean
  review_verdict: string | null
}

// ===========================================
// CONSTANTS
// ===========================================

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  active: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    dot: 'bg-green-500',
  },
  completed: {
    bg: 'bg-blue-100',
    text: 'text-blue-800',
    dot: 'bg-blue-500',
  },
  paused: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    dot: 'bg-yellow-500',
  },
  abandoned: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    dot: 'bg-red-500',
  },
  wrapping_up: {
    bg: 'bg-orange-100',
    text: 'text-orange-800',
    dot: 'bg-orange-500',
  },
}

function getStatusStyle(status: string): { bg: string; text: string; dot: string } {
  return STATUS_COLORS[status.toLowerCase()] ?? {
    bg: 'bg-gray-100',
    text: 'text-gray-800',
    dot: 'bg-gray-500',
  }
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

function StatusBadge({ status }: { status: string }) {
  const style = getStatusStyle(status)
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function DateRange({
  startedAt,
  actualEndAt,
}: {
  startedAt: string
  actualEndAt: string | null
}) {
  const start = new Date(startedAt).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  const end = actualEndAt
    ? new Date(actualEndAt).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Ongoing'

  return (
    <span className="text-xs text-muted-foreground">
      {start} &mdash; {end}
    </span>
  )
}

function StatsRow({
  claims,
  findings,
  reviews,
}: {
  claims: number
  findings: number
  reviews: number
}) {
  return (
    <div className="flex items-center gap-4 text-xs text-muted-foreground">
      <span className="flex items-center gap-1">
        <span className="font-medium text-foreground">{claims}</span>
        {claims === 1 ? 'claim' : 'claims'}
      </span>
      <span className="flex items-center gap-1">
        <span className="font-medium text-foreground">{findings}</span>
        {findings === 1 ? 'finding' : 'findings'}
      </span>
      <span className="flex items-center gap-1">
        <span className="font-medium text-foreground">{reviews}</span>
        {reviews === 1 ? 'review' : 'reviews'}
      </span>
    </div>
  )
}

function SprintCard({
  sprint,
  isLast,
}: {
  sprint: Sprint
  isLast: boolean
}) {
  const statusStyle = getStatusStyle(sprint.status)

  return (
    <div className="relative flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        {/* Dot */}
        <div
          className={`z-10 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 border-background ${statusStyle.dot}`}
        />
        {/* Vertical line */}
        {!isLast && (
          <div className="w-0.5 flex-1 bg-border" />
        )}
      </div>

      {/* Card */}
      <div className="mb-6 flex-1 pb-1">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <CardTitle className="text-base font-semibold">
                  Sprint {sprint.sprint_number}
                </CardTitle>
                <p className="mt-1 text-sm text-foreground line-clamp-2">
                  {sprint.goal}
                </p>
              </div>
              <StatusBadge status={sprint.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Date range */}
            <DateRange
              startedAt={sprint.started_at}
              actualEndAt={sprint.actual_end_at}
            />

            {/* Outcome (if completed) */}
            {sprint.outcome_type && (
              <div className="rounded-md border bg-muted/50 p-3">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-medium capitalize">
                    {sprint.outcome_type.replace(/_/g, ' ')}
                  </span>
                </div>
                {sprint.outcome_summary && (
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-3">
                    {sprint.outcome_summary}
                  </p>
                )}
              </div>
            )}

            {/* Stats */}
            <StatsRow
              claims={sprint.claims_submitted}
              findings={sprint.findings_recorded}
              reviews={sprint.reviews_completed}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

interface SprintTimelineProps {
  agentId: string
}

export default function SprintTimeline({ agentId }: SprintTimelineProps) {
  const [sprints, setSprints] = useState<Sprint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchSprints() {
      setLoading(true)
      setError(null)

      try {
        const response = await apiClient.get<Sprint[]>(
          `/lifecycle/agents/${agentId}/sprints`
        )
        if (!cancelled) {
          // Sort by sprint_number descending (most recent first)
          const sorted = [...response.data].sort(
            (a, b) => b.sprint_number - a.sprint_number
          )
          setSprints(sorted)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load sprint data'
          setError(message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchSprints()

    return () => {
      cancelled = true
    }
  }, [agentId])

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

  // ------ Empty ------
  if (sprints.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-muted-foreground">No sprint history available.</p>
      </div>
    )
  }

  // ------ Timeline ------
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground mb-4">
        Sprint History ({sprints.length} {sprints.length === 1 ? 'sprint' : 'sprints'})
      </h3>
      <div className="pl-1">
        {sprints.map((sprint, index) => (
          <SprintCard
            key={sprint.id}
            sprint={sprint}
            isLast={index === sprints.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
