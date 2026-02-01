/**
 * ExperiencePanel -- Displays an agent's experience profile including level,
 * tier, prestige, domain XP bars, role XP breakdown, and recent milestones.
 */

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import {
  getAgentExperience,
  getAgentMilestones,
} from '@/api/experience'
import type { ExperienceResponse, DomainXPDetail, MilestoneResponse } from '@/types/experience'

// ===========================================
// CONSTANTS
// ===========================================

const TIER_COLORS: Record<string, string> = {
  novice: '#888888',
  contributor: '#4169E1',
  specialist: '#32CD32',
  expert: '#9370DB',
  master: '#FFD700',
  grandmaster: '#FF4500',
}

function getTierColor(tier: string): string {
  return TIER_COLORS[tier.toLowerCase()] ?? TIER_COLORS.novice
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

function PrestigeStars({ count }: { count: number }) {
  if (count <= 0) return null
  return (
    <span className="ml-2 text-yellow-400 text-lg" title={`Prestige ${count}`}>
      {Array.from({ length: count }, (_, i) => (
        <span key={i}>&#9733;</span>
      ))}
    </span>
  )
}

function XPProgressBar({
  label,
  current,
  max,
  color,
}: {
  label: string
  current: number
  max: number
  color: string
}) {
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium capitalize">{label}</span>
        <span className="text-muted-foreground">
          {current.toLocaleString()} / {max.toLocaleString()} XP
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-secondary">
        <div
          className="h-2 rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

function DomainXPBars({ domains }: { domains: DomainXPDetail[] }) {
  if (domains.length === 0) {
    return <p className="text-sm text-muted-foreground">No domain experience yet.</p>
  }
  return (
    <div className="space-y-3">
      {domains.map((d) => (
        <div key={d.domain}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="font-medium capitalize">
              {d.domain.replace(/_/g, ' ')}
            </span>
            <span className="text-muted-foreground">Level {d.level}</span>
          </div>
          <div className="h-2 w-full rounded-full bg-secondary">
            <div
              className="h-2 rounded-full bg-blue-500 transition-all duration-300"
              style={{
                width:
                  d.xp_to_next_level > 0
                    ? `${Math.min((d.xp / (d.xp + d.xp_to_next_level)) * 100, 100)}%`
                    : '100%',
              }}
            />
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {d.xp.toLocaleString()} XP &middot; {d.xp_to_next_level.toLocaleString()} to next
          </p>
        </div>
      ))}
    </div>
  )
}

function RoleXPBreakdown({ roleXP }: { roleXP: Record<string, number> }) {
  const entries = Object.entries(roleXP)
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No role experience yet.</p>
  }
  const maxXP = Math.max(...entries.map(([, xp]) => xp), 1)
  return (
    <div className="space-y-2">
      {entries.map(([role, xp]) => (
        <div key={role} className="flex items-center gap-3">
          <span className="w-28 text-xs font-medium capitalize truncate">
            {role.replace(/_/g, ' ')}
          </span>
          <div className="flex-1 h-2 rounded-full bg-secondary">
            <div
              className="h-2 rounded-full bg-purple-500 transition-all duration-300"
              style={{ width: `${(xp / maxXP) * 100}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-16 text-right">
            {xp.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  )
}

function MilestonesList({ milestones }: { milestones: MilestoneResponse[] }) {
  if (milestones.length === 0) {
    return <p className="text-sm text-muted-foreground">No milestones unlocked yet.</p>
  }
  return (
    <div className="space-y-2">
      {milestones.slice(0, 5).map((m) => (
        <div
          key={m.milestone_slug}
          className="flex items-start gap-3 rounded-md border p-3"
        >
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700 text-sm font-bold">
            M
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{m.name}</p>
            <p className="text-xs text-muted-foreground line-clamp-2">{m.description}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {new Date(m.unlocked_at).toLocaleDateString()}
              {' '}&middot;{' '}
              <span className="capitalize">{m.category}</span>
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

interface ExperiencePanelProps {
  agentId: string
}

export default function ExperiencePanel({ agentId }: ExperiencePanelProps) {
  const [experience, setExperience] = useState<ExperienceResponse | null>(null)
  const [milestones, setMilestones] = useState<MilestoneResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchData() {
      setLoading(true)
      setError(null)

      try {
        const [xpData, msData] = await Promise.all([
          getAgentExperience(agentId),
          getAgentMilestones(agentId),
        ])
        if (!cancelled) {
          setExperience(xpData)
          setMilestones(msData)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load experience data'
          setError(message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchData()

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
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    )
  }

  // ------ No data ------
  if (!experience) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-muted-foreground">No experience data available.</p>
      </div>
    )
  }

  const tierColor = getTierColor(experience.tier)

  // Calculate XP progress within current level.
  // total_xp is cumulative; we derive in-level progress from domain totals as a proxy,
  // but the simplest display uses total_xp with the global_level.
  // For the main bar we show total XP towards next level boundary.
  // A simple heuristic: next-level XP = (level + 1) * 1000
  const nextLevelXP = (experience.global_level + 1) * 1000
  const currentLevelBase = experience.global_level * 1000
  const xpInLevel = experience.total_xp - currentLevelBase
  const xpNeeded = nextLevelXP - currentLevelBase

  return (
    <div className="space-y-6">
      {/* ---- Top: Level + Tier + Prestige ---- */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-6">
            {/* Level badge */}
            <div
              className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4"
              style={{ borderColor: tierColor }}
            >
              <span className="text-3xl font-bold" style={{ color: tierColor }}>
                {experience.global_level}
              </span>
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold text-white"
                  style={{ backgroundColor: tierColor }}
                >
                  {experience.tier.charAt(0).toUpperCase() + experience.tier.slice(1)}
                </span>
                <PrestigeStars count={experience.prestige_count} />
                {experience.prestige_bonus > 0 && (
                  <span className="text-xs text-muted-foreground">
                    +{(experience.prestige_bonus * 100).toFixed(0)}% bonus
                  </span>
                )}
              </div>

              <p className="text-sm text-muted-foreground mt-1">
                {experience.total_xp.toLocaleString()} total XP
              </p>

              {/* Main XP bar */}
              <div className="mt-3">
                <XPProgressBar
                  label={`Level ${experience.global_level}`}
                  current={Math.max(xpInLevel, 0)}
                  max={xpNeeded}
                  color={tierColor}
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ---- Bottom: Domain + Role + Milestones ---- */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Domain XP */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Domain Experience</CardTitle>
          </CardHeader>
          <CardContent>
            <DomainXPBars domains={experience.domains} />
          </CardContent>
        </Card>

        {/* Role XP */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Role Experience</CardTitle>
          </CardHeader>
          <CardContent>
            <RoleXPBreakdown roleXP={experience.role_xp} />
          </CardContent>
        </Card>
      </div>

      {/* Milestones */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Recent Milestones</CardTitle>
        </CardHeader>
        <CardContent>
          <MilestonesList milestones={milestones} />
        </CardContent>
      </Card>
    </div>
  )
}
