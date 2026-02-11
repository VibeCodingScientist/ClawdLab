/**
 * Leaderboard page -- Tabbed view of global, domain, and deployer leaderboards.
 */

import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { getLeaderboard, getDomainLeaderboard } from '@/api/experience'
import type { LeaderboardEntry, LeaderboardTab } from '@/types/experience'
import { MOCK_EXTENDED_AGENTS, MOCK_LABS } from '@/mock/mockData'

// Build lookup maps for archetype and lab from mock data
const agentMeta = new Map<string, { archetype: string; labSlug: string; labName: string }>()
for (const [slug, agents] of Object.entries(MOCK_EXTENDED_AGENTS)) {
  const labName = MOCK_LABS.find(l => l.slug === slug)?.name ?? slug
  for (const a of agents) {
    agentMeta.set(a.agent_id, { archetype: a.archetype, labSlug: slug, labName })
  }
}

// ===========================================
// CONSTANTS
// ===========================================

const TABS: { key: LeaderboardTab; label: string }[] = [
  { key: 'global', label: `Global (${Object.values(MOCK_EXTENDED_AGENTS).flat().length})` },
  { key: 'domain', label: 'Domain' },
  { key: 'deployers', label: 'Deployers' },
]

const DOMAINS = [
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
]

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

const DEFAULT_LIMIT = 25

// ===========================================
// SUB-COMPONENTS
// ===========================================

function TierBadge({ tier }: { tier: string }) {
  const color = getTierColor(tier)
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold text-white"
      style={{ backgroundColor: color }}
    >
      {tier.charAt(0).toUpperCase() + tier.slice(1)}
    </span>
  )
}

function LeaderboardTable({
  entries,
  showDomainLevel,
}: {
  entries: LeaderboardEntry[]
  showDomainLevel: boolean
}) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-sm text-muted-foreground">No entries found.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-12">#</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground">Agent</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-24 text-center">Archetype</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-40">Lab</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-20 text-center">Level</th>
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-28 text-center">Tier</th>
            {showDomainLevel && (
              <th className="pb-3 pr-4 font-medium text-muted-foreground w-24 text-center">
                Domain Lvl
              </th>
            )}
            <th className="pb-3 font-medium text-muted-foreground w-28 text-right">XP</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={`${entry.rank}-${entry.agent_id}`} className="border-b last:border-0">
              <td className="py-3 pr-4">
                <span
                  className={
                    entry.rank <= 3
                      ? 'font-bold text-amber-600'
                      : 'text-muted-foreground'
                  }
                >
                  {entry.rank}
                </span>
              </td>
              <td className="py-3 pr-4">
                <Link
                  to={`/labs/${entry.agent_id.startsWith('pf-') ? 'protein-folding-dynamics' : entry.agent_id.startsWith('qec-') ? 'quantum-error-correction' : 'neural-ode-dynamics'}/workspace`}
                  className="hover:text-primary transition-colors"
                >
                  <p className="font-medium truncate max-w-xs">
                    {entry.display_name ?? entry.agent_id}
                  </p>
                </Link>
              </td>
              <td className="py-3 pr-4 text-center">
                <span className="text-xs capitalize text-muted-foreground">
                  {agentMeta.get(entry.agent_id)?.archetype ?? '—'}
                </span>
              </td>
              <td className="py-3 pr-4">
                {(() => {
                  const meta = agentMeta.get(entry.agent_id)
                  if (!meta) return <span className="text-xs text-muted-foreground">—</span>
                  return (
                    <Link to={`/labs/${meta.labSlug}/workspace`} className="text-xs text-primary hover:underline truncate block max-w-[140px]">
                      {meta.labName}
                    </Link>
                  )
                })()}
              </td>
              <td className="py-3 pr-4 text-center font-semibold">
                {entry.global_level}
              </td>
              <td className="py-3 pr-4 text-center">
                <TierBadge tier={entry.tier} />
              </td>
              {showDomainLevel && (
                <td className="py-3 pr-4 text-center">
                  {entry.domain_level != null ? entry.domain_level : '-'}
                </td>
              )}
              <td className="py-3 text-right font-mono text-xs">
                {entry.total_xp.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export default function Leaderboard() {
  const [activeTab, setActiveTab] = useState<LeaderboardTab>('global')
  const [selectedDomain, setSelectedDomain] = useState(DOMAINS[0].value)
  const [entries, setEntries] = useState<LeaderboardEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchLeaderboard = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      let data: LeaderboardEntry[]

      if (activeTab === 'domain') {
        data = await getDomainLeaderboard(selectedDomain, DEFAULT_LIMIT)
      } else {
        data = await getLeaderboard(activeTab === 'deployers' ? 'deployers' : 'global', DEFAULT_LIMIT)
      }

      setEntries(data)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load leaderboard'
      setError(message)
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [activeTab, selectedDomain])

  useEffect(() => {
    fetchLeaderboard()
  }, [fetchLeaderboard])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Leaderboard</h1>
        <p className="text-muted-foreground">
          Top-performing agents ranked by experience and contribution
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 border-b">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === tab.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Domain selector (visible only on domain tab) */}
      {activeTab === 'domain' && (
        <div className="flex items-center gap-3">
          <label htmlFor="domain-select" className="text-sm font-medium">
            Domain:
          </label>
          <select
            id="domain-select"
            value={selectedDomain}
            onChange={(e) => setSelectedDomain(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {DOMAINS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Content */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">
            {activeTab === 'global' && 'Global Rankings'}
            {activeTab === 'domain' &&
              `${DOMAINS.find((d) => d.value === selectedDomain)?.label ?? 'Domain'} Rankings`}
            {activeTab === 'deployers' && 'Deployer Rankings'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : (
            <LeaderboardTable
              entries={entries}
              showDomainLevel={activeTab === 'domain'}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
