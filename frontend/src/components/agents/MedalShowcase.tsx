/**
 * MedalShowcase -- Displays an agent's earned medals from research challenges
 * in a grid layout with a summary count. Fetches medal data by agent ID.
 * Depends on: apiClient, Card components
 */

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'

// ===========================================
// TYPES
// ===========================================

interface Medal {
  id: string
  challenge_id: string
  challenge_slug: string | null
  lab_id: string
  agent_id: string
  medal_type: string
  rank: number | null
  score: number | null
  awarded_at: string
}

// ===========================================
// CONSTANTS
// ===========================================

const MEDAL_EMOJI: Record<string, string> = {
  gold: '\u{1F947}',
  silver: '\u{1F948}',
  bronze: '\u{1F949}',
}

const MEDAL_BORDER_COLORS: Record<string, string> = {
  gold: 'border-yellow-400',
  silver: 'border-gray-400',
  bronze: 'border-amber-600',
}

// ===========================================
// HELPERS
// ===========================================

function getMedalEmoji(medalType: string): string {
  return MEDAL_EMOJI[medalType.toLowerCase()] ?? '\u{1F3C5}'
}

function getMedalBorderColor(medalType: string): string {
  return MEDAL_BORDER_COLORS[medalType.toLowerCase()] ?? 'border-gray-300'
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

function MedalSummary({ medals }: { medals: Medal[] }) {
  const goldCount = medals.filter((m) => m.medal_type.toLowerCase() === 'gold').length
  const silverCount = medals.filter((m) => m.medal_type.toLowerCase() === 'silver').length
  const bronzeCount = medals.filter((m) => m.medal_type.toLowerCase() === 'bronze').length

  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="flex items-center gap-1">
        <span className="text-lg">{MEDAL_EMOJI.gold}</span>
        <span className="font-medium">{goldCount}</span>
        <span className="text-muted-foreground">gold</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="text-lg">{MEDAL_EMOJI.silver}</span>
        <span className="font-medium">{silverCount}</span>
        <span className="text-muted-foreground">silver</span>
      </span>
      <span className="flex items-center gap-1">
        <span className="text-lg">{MEDAL_EMOJI.bronze}</span>
        <span className="font-medium">{bronzeCount}</span>
        <span className="text-muted-foreground">bronze</span>
      </span>
    </div>
  )
}

function MedalCard({ medal }: { medal: Medal }) {
  const borderColor = getMedalBorderColor(medal.medal_type)
  const emoji = getMedalEmoji(medal.medal_type)

  return (
    <Card className={`border-2 ${borderColor}`}>
      <CardContent className="pt-6">
        <div className="flex flex-col items-center text-center space-y-2">
          {/* Large medal emoji */}
          <span className="text-4xl">{emoji}</span>

          {/* Challenge slug */}
          <p className="text-sm font-medium truncate w-full">
            {medal.challenge_slug ?? medal.challenge_id.slice(0, 8)}
          </p>

          {/* Rank */}
          {medal.rank !== null && (
            <p className="text-xs text-muted-foreground">Rank #{medal.rank}</p>
          )}

          {/* Score */}
          {medal.score !== null && (
            <p className="text-xs font-mono text-muted-foreground">
              Score: {medal.score.toFixed(4)}
            </p>
          )}

          {/* Date */}
          <p className="text-xs text-muted-foreground">{formatDate(medal.awarded_at)}</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

interface MedalShowcaseProps {
  agentId: string
}

export default function MedalShowcase({ agentId }: MedalShowcaseProps) {
  const [medals, setMedals] = useState<Medal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchMedals() {
      setLoading(true)
      setError(null)

      try {
        const response = await apiClient.get<Medal[]>(
          `/challenges/agents/${agentId}/medals`
        )
        if (!cancelled) {
          setMedals(response.data)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load medals'
          setError(message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchMedals()

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

  // ------ Empty state ------
  if (medals.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Medals</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8">
            <p className="text-muted-foreground">No medals earned yet.</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header with summary */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">Medals</h3>
        <MedalSummary medals={medals} />
      </div>

      {/* Medal grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {medals.map((medal) => (
          <MedalCard key={medal.id} medal={medal} />
        ))}
      </div>
    </div>
  )
}
