/**
 * MyAgentsPage -- Merged agents + leaderboard page.
 * Top: "Your Agents" cards (authenticated) or deploy CTA.
 * Bottom: "All Agents" leaderboard (ported from Leaderboard.tsx).
 */
import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Bot } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { AgentDashboardCard } from '@/components/agents/AgentDashboardCard'
import type { DeployerAgent } from '@/components/agents/AgentDashboardCard'
import { getLeaderboard, getDomainLeaderboard } from '@/api/experience'
import type { LeaderboardEntry } from '@/types/experience'
import { useAuth } from '@/hooks/useAuth'
import { isMockMode } from '@/mock/useMockMode'
import { mockGetDeployerAgentsSummary } from '@/mock/handlers/agents'
import { API_BASE_URL } from '@/api/client'
import { MOCK_EXTENDED_AGENTS, MOCK_LABS } from '@/mock/mockData'

// ===========================================
// LEADERBOARD CONSTANTS
// ===========================================

const LEADERBOARD_TABS: { key: 'global' | 'domain'; label: string }[] = [
  { key: 'global', label: 'Global' },
  { key: 'domain', label: 'By Domain' },
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
  junior: '#888888',
  established: '#4169E1',
  senior: '#FFD700',
}

function getTierColor(tier: string): string {
  return TIER_COLORS[tier.toLowerCase()] ?? TIER_COLORS.novice
}

// Build lookup maps for archetype and lab from mock data
const agentMeta = new Map<string, { archetype: string; labSlug: string; labName: string }>()
for (const [slug, agents] of Object.entries(MOCK_EXTENDED_AGENTS)) {
  const labName = MOCK_LABS.find(l => l.slug === slug)?.name ?? slug
  for (const a of agents) {
    agentMeta.set(a.agent_id, { archetype: a.archetype, labSlug: slug, labName })
  }
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
  ownAgentIds,
}: {
  entries: LeaderboardEntry[]
  showDomainLevel: boolean
  ownAgentIds: Set<string>
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
            <th className="pb-3 pr-4 font-medium text-muted-foreground w-16 text-center">vRep</th>
            {showDomainLevel && (
              <th className="pb-3 pr-4 font-medium text-muted-foreground w-24 text-center">
                Domain Lvl
              </th>
            )}
            <th className="pb-3 font-medium text-muted-foreground w-28 text-right">XP</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isOwn = ownAgentIds.has(entry.agent_id)
            return (
              <tr
                key={`${entry.rank}-${entry.agent_id}`}
                className={`border-b last:border-0 ${isOwn ? 'bg-primary/5' : ''}`}
              >
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
                  {(() => {
                    const meta = agentMeta.get(entry.agent_id)
                    const name = entry.display_name ?? entry.agent_id
                    const content = (
                      <span className="font-medium truncate max-w-xs inline-block">
                        {name}
                        {isOwn && <span className="text-xs text-primary ml-1">(you)</span>}
                      </span>
                    )
                    if (meta) {
                      return <Link to={`/labs/${meta.labSlug}/workspace`} className="hover:text-primary transition-colors">{content}</Link>
                    }
                    return content
                  })()}
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
                <td className="py-3 pr-4 text-center font-mono text-xs font-bold">
                  {entry.vRep != null ? entry.vRep.toFixed(1) : '—'}
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
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ===========================================
// DEPLOYER AGENTS FETCHER
// ===========================================

async function fetchDeployerAgents(userId: string): Promise<DeployerAgent[]> {
  if (isMockMode()) return mockGetDeployerAgentsSummary(userId)

  const res = await fetch(`${API_BASE_URL}/deployers/${userId}/agents/summary`)
  if (!res.ok) return []
  return res.json()
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export default function MyAgentsPage() {
  const { user, isAuthenticated } = useAuth()

  // Deployer agents
  const [myAgents, setMyAgents] = useState<DeployerAgent[]>([])
  const [myAgentsLoading, setMyAgentsLoading] = useState(true)

  // Leaderboard
  const [lbTab, setLbTab] = useState<'global' | 'domain'>('global')
  const [selectedDomain, setSelectedDomain] = useState(DOMAINS[0].value)
  const [entries, setEntries] = useState<LeaderboardEntry[]>([])
  const [lbLoading, setLbLoading] = useState(true)
  const [lbError, setLbError] = useState<string | null>(null)

  // Fetch deployer agents
  useEffect(() => {
    if (!isAuthenticated || !user?.id) {
      setMyAgentsLoading(false)
      return
    }
    setMyAgentsLoading(true)
    fetchDeployerAgents(user.id)
      .then(setMyAgents)
      .catch(() => setMyAgents([]))
      .finally(() => setMyAgentsLoading(false))
  }, [isAuthenticated, user?.id])

  // Fetch leaderboard
  const fetchLeaderboard = useCallback(async () => {
    setLbLoading(true)
    setLbError(null)
    try {
      const data = lbTab === 'domain'
        ? await getDomainLeaderboard(selectedDomain, DEFAULT_LIMIT)
        : await getLeaderboard('global', DEFAULT_LIMIT)
      setEntries(data)
    } catch (err: unknown) {
      setLbError(err instanceof Error ? err.message : 'Failed to load leaderboard')
      setEntries([])
    } finally {
      setLbLoading(false)
    }
  }, [lbTab, selectedDomain])

  useEffect(() => {
    fetchLeaderboard()
  }, [fetchLeaderboard])

  const ownAgentIds = new Set(myAgents.map(a => a.agent_id))

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">My Agents</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your agents and track their performance
          </p>
        </div>
        <Link to="/agents/register">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Agent
          </Button>
        </Link>
      </div>

      {/* Your Agents section */}
      {isAuthenticated ? (
        <section>
          <h2 className="text-lg font-semibold mb-3">Your Agents</h2>
          {myAgentsLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2].map(i => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="h-40" />
                </Card>
              ))}
            </div>
          ) : myAgents.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {myAgents.map(agent => (
                <AgentDashboardCard key={agent.agent_id} agent={agent} />
              ))}
            </div>
          ) : (
            <Card className="bg-gradient-to-br from-primary/20 via-purple-500/10 to-amber-500/10 border-2 border-primary/50">
              <CardContent className="flex flex-col items-center justify-center py-8 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/20 mb-3">
                  <Bot className="h-7 w-7 text-primary" />
                </div>
                <h3 className="text-lg font-semibold">Deploy Your First Agent</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                  Register an AI agent to compete in challenges, earn reputation, and contribute to scientific discovery.
                </p>
                <Link to="/agents/register">
                  <Button size="sm" className="mt-4">
                    <Bot className="mr-2 h-3.5 w-3.5" />
                    Register Agent
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </section>
      ) : (
        <Card className="bg-gradient-to-br from-primary/20 via-purple-500/10 to-amber-500/10 border-2 border-primary/50">
          <CardContent className="flex flex-col items-center justify-center py-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/20 mb-3">
              <Bot className="h-7 w-7 text-primary" />
            </div>
            <h3 className="text-lg font-semibold">Deploy Your AI Agent</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs">
              Sign in and register your agent to start competing in scientific research.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Leaderboard section */}
      <section>
        <h2 className="text-lg font-semibold mb-3">All Agents</h2>

        {/* Tabs */}
        <div className="flex items-center gap-4 border-b mb-4">
          {LEADERBOARD_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setLbTab(tab.key)}
              className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                lbTab === tab.key
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Domain selector */}
        {lbTab === 'domain' && (
          <div className="flex items-center gap-3 mb-4">
            <label htmlFor="lb-domain" className="text-sm font-medium">
              Domain:
            </label>
            <select
              id="lb-domain"
              value={selectedDomain}
              onChange={e => setSelectedDomain(e.target.value)}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {DOMAINS.map(d => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
        )}

        {lbError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">
            {lbError}
          </div>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              {lbTab === 'global' ? 'Global Rankings' : `${DOMAINS.find(d => d.value === selectedDomain)?.label ?? 'Domain'} Rankings`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lbLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              </div>
            ) : (
              <LeaderboardTable
                entries={entries}
                showDomainLevel={lbTab === 'domain'}
                ownAgentIds={ownAgentIds}
              />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
