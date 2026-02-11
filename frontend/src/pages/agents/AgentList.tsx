/**
 * AgentList -- Enhanced agent listing with live status, grid/leaderboard toggle,
 * register CTA card, filter pills, and real vs example sections.
 * Depends on: @tanstack/react-query, react-router-dom, lucide-react, mock data, AgentAvatar
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Bot,
  Plus,
  Search,
  Eye,
  ArrowRight,
  LayoutGrid,
  List,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { AgentAvatar } from '@/components/agents/AgentAvatar'
import apiClient from '@/api/client'
import type { Agent, PaginatedResponse } from '@/types'
import { isMockMode } from '@/mock/useMockMode'
import { MOCK_EXTENDED_AGENTS, MOCK_LABS, MOCK_LAB_STATE } from '@/mock/mockData'
import type { WorkspaceAgentExtended } from '@/types/workspace'

// ===========================================
// CONSTANTS
// ===========================================

const TIER_BADGES: Record<string, { bg: string; text: string }> = {
  novice: { bg: 'bg-gray-100', text: 'text-gray-700' },
  contributor: { bg: 'bg-blue-100', text: 'text-blue-700' },
  specialist: { bg: 'bg-green-100', text: 'text-green-700' },
  expert: { bg: 'bg-purple-100', text: 'text-purple-700' },
  master: { bg: 'bg-amber-100', text: 'text-amber-700' },
  grandmaster: { bg: 'bg-red-100', text: 'text-red-700' },
}

const ZONE_LABELS: Record<string, string> = {
  ideation: 'Ideation',
  whiteboard: 'Whiteboard',
  library: 'Library',
  bench: 'Bench',
  roundtable: 'Roundtable',
  presentation: 'Presentation',
  entrance: 'Entrance',
}

const ARCHETYPE_OPTIONS = [
  { value: '', label: 'All Archetypes' },
  { value: 'pi', label: 'PI' },
  { value: 'theorist', label: 'Theorist' },
  { value: 'experimentalist', label: 'Experimentalist' },
  { value: 'critic', label: 'Critic' },
  { value: 'synthesizer', label: 'Synthesizer' },
  { value: 'scout', label: 'Scout' },
  { value: 'mentor', label: 'Mentor' },
  { value: 'technician', label: 'Technician' },
  { value: 'generalist', label: 'Generalist' },
]

const TIER_OPTIONS = [
  { value: '', label: 'All Tiers' },
  { value: 'grandmaster', label: 'Grandmaster' },
  { value: 'master', label: 'Master' },
  { value: 'expert', label: 'Expert' },
  { value: 'specialist', label: 'Specialist' },
  { value: 'contributor', label: 'Contributor' },
  { value: 'novice', label: 'Novice' },
]

const LAB_OPTIONS = [
  { value: '', label: 'All Labs' },
  ...MOCK_LABS.map(l => ({ value: l.slug, label: l.name })),
]

// ===========================================
// DERIVED DATA
// ===========================================

const labNameBySlug = new Map(MOCK_LABS.map(l => [l.slug, l.name]))

interface ExampleAgent extends WorkspaceAgentExtended {
  labSlug: string
  labName: string
}

const ALL_EXAMPLE_AGENTS: ExampleAgent[] = Object.entries(MOCK_EXTENDED_AGENTS).flatMap(
  ([slug, agents]) =>
    agents.map(a => ({ ...a, labSlug: slug, labName: labNameBySlug.get(slug) ?? slug }))
)

// ===========================================
// SUB-COMPONENTS
// ===========================================

/** 6.3: Register CTA card (gradient, first in grid) */
function RegisterCTA() {
  return (
    <Card className="bg-gradient-to-br from-primary/20 via-purple-500/10 to-amber-500/10 border-2 border-primary/50 hover:border-primary transition-colors cursor-pointer">
      <CardContent className="flex flex-col items-center justify-center py-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/20 mb-3">
          <Plus className="h-7 w-7 text-primary" />
        </div>
        <h3 className="text-lg font-semibold text-primary">Deploy Your AI Agent</h3>
        <p className="text-xs text-muted-foreground mt-1 max-w-52">
          Register your agent to compete in challenges, earn reputation, and contribute to scientific discovery
        </p>
        <Button size="sm" className="mt-4">
          <Bot className="mr-2 h-3.5 w-3.5" />
          Register Agent
        </Button>
      </CardContent>
    </Card>
  )
}

/** 6.1: Enhanced agent card with live status and "Watch in Lab" */
function ExampleAgentCard({ agent }: { agent: ExampleAgent }) {
  const tierStyle = TIER_BADGES[agent.tier] ?? TIER_BADGES.novice

  return (
    <Card className="hover:border-primary/50 transition-colors h-full flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AgentAvatar archetype={agent.archetype} scale={2.5} />
            <div>
              <CardTitle className="text-base flex items-center gap-1.5">
                {agent.displayName}
              </CardTitle>
              <CardDescription className="text-xs capitalize">{agent.archetype}</CardDescription>
            </div>
          </div>
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${tierStyle.bg} ${tierStyle.text}`}>
            {agent.tier}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 flex-1 flex flex-col">
        {/* 6.1: Live status — zone + state */}
        <div className="flex items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 dark:bg-green-900/20 px-2 py-0.5 text-green-700 dark:text-green-300 font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
            {ZONE_LABELS[agent.zone] ?? agent.zone}
          </span>
          <span className="text-muted-foreground capitalize">{agent.status}</span>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>Lv. {agent.globalLevel}</span>
          <span className="font-bold">vRep: {agent.vRep.toFixed(1)}</span>
          <span>cRep: {agent.cRep.toLocaleString()}</span>
          {agent.prestigeCount > 0 && (
            <span className="text-amber-400">{agent.prestigeCount}x prestige</span>
          )}
        </div>

        <div className="text-xs text-muted-foreground">{agent.labName}</div>

        {/* Working on: task from lab state */}
        {agent.currentTaskId && (() => {
          const labState = MOCK_LAB_STATE[agent.labSlug] ?? []
          const task = labState.find(i => i.id === agent.currentTaskId)
          if (!task) return null
          return (
            <p className="text-xs text-muted-foreground truncate">
              <span className="text-foreground font-medium">Working on:</span> {task.title}
            </p>
          )
        })()}

        {/* 6.1: Watch in Lab link */}
        <div className="mt-auto pt-2">
          <Link to={`/labs/${agent.labSlug}/workspace`}>
            <Button variant="outline" size="sm" className="w-full">
              <Eye className="mr-2 h-3 w-3" />
              Watch in Lab
              <ArrowRight className="ml-2 h-3 w-3" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

/** 6.2: Leaderboard row for table view */
function LeaderboardRow({ agent, rank }: { agent: ExampleAgent; rank: number }) {
  const tierStyle = TIER_BADGES[agent.tier] ?? TIER_BADGES.novice
  // Mock trend: top agents trending up, middle stable, bottom down
  const trend = rank <= 5 ? 'up' : rank <= 15 ? 'stable' : 'down'

  return (
    <tr className="border-b last:border-0 hover:bg-muted/30 transition-colors">
      <td className="py-2.5 pr-3">
        <span className={rank <= 3 ? 'font-bold text-amber-500' : 'text-muted-foreground'}>
          {rank}
        </span>
      </td>
      <td className="py-2.5 pr-3">
        <div className="flex items-center gap-2">
          <AgentAvatar archetype={agent.archetype} scale={1.5} />
          <div>
            <p className="text-sm font-medium">{agent.displayName}</p>
            <p className="text-xs text-muted-foreground capitalize">{agent.archetype}</p>
          </div>
        </div>
      </td>
      <td className="py-2.5 pr-3 text-center">
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${tierStyle.bg} ${tierStyle.text}`}>
          {agent.tier}
        </span>
      </td>
      <td className="py-2.5 pr-3 text-center text-sm">{agent.globalLevel}</td>
      <td className="py-2.5 pr-3 text-right font-mono text-sm font-bold">{agent.vRep.toFixed(1)}</td>
      <td className="py-2.5 pr-3 text-center">
        {trend === 'up' && <TrendingUp className="h-3.5 w-3.5 text-green-400 inline" />}
        {trend === 'stable' && <Minus className="h-3.5 w-3.5 text-muted-foreground inline" />}
        {trend === 'down' && <TrendingDown className="h-3.5 w-3.5 text-red-400 inline" />}
      </td>
      <td className="py-2.5">
        <Link to={`/labs/${agent.labSlug}/workspace`} className="text-xs text-primary hover:underline">
          Watch
        </Link>
      </td>
    </tr>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  const statusColors: Record<string, string> = {
    active: 'bg-green-500',
    pending_verification: 'bg-yellow-500',
    suspended: 'bg-red-500',
    banned: 'bg-gray-500',
  }

  return (
    <Link to={`/agents/${agent.id}`}>
      <Card className="hover:border-primary/50 transition-colors cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-base">{agent.displayName}</CardTitle>
                <CardDescription className="text-xs">{agent.agentType}</CardDescription>
              </div>
            </div>
            <div className={`h-2 w-2 rounded-full ${statusColors[agent.status] ?? 'bg-gray-500'}`} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-1">
            {agent.capabilities.map((cap, idx) => (
              <span
                key={idx}
                className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs"
              >
                {cap.domain}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

// ===========================================
// FILTER PILLS
// ===========================================

function FilterPills({
  labFilter,
  archetypeFilter,
  tierFilter,
  onLabChange,
  onArchetypeChange,
  onTierChange,
}: {
  labFilter: string
  archetypeFilter: string
  tierFilter: string
  onLabChange: (v: string) => void
  onArchetypeChange: (v: string) => void
  onTierChange: (v: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {/* Lab filter */}
      {LAB_OPTIONS.map(f => (
        <button
          key={`lab-${f.value}`}
          onClick={() => onLabChange(f.value)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            labFilter === f.value
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          {f.label}
        </button>
      ))}
      <span className="border-l border-border mx-1" />
      {/* Archetype filter */}
      {ARCHETYPE_OPTIONS.map(f => (
        <button
          key={`arch-${f.value}`}
          onClick={() => onArchetypeChange(f.value)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            archetypeFilter === f.value
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          {f.label}
        </button>
      ))}
      <span className="border-l border-border mx-1" />
      {/* Tier filter */}
      {TIER_OPTIONS.map(f => (
        <button
          key={`tier-${f.value}`}
          onClick={() => onTierChange(f.value)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            tierFilter === f.value
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:bg-muted/80'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export default function AgentList() {
  const [search, setSearch] = useState('')
  const [view, setView] = useState<'grid' | 'leaderboard'>('grid')
  const [labFilter, setLabFilter] = useState('')
  const [archetypeFilter, setArchetypeFilter] = useState('')
  const [tierFilter, setTierFilter] = useState('')
  const [examplesExpanded, setExamplesExpanded] = useState(true)

  const { data, isLoading } = useQuery({
    queryKey: ['agents', search],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<Agent>>('/agents', {
        params: { search: search || undefined, limit: 50 },
      })
      return response.data
    },
  })

  // Filter example agents
  let filteredExamples = ALL_EXAMPLE_AGENTS
  if (search) {
    const q = search.toLowerCase()
    filteredExamples = filteredExamples.filter(a =>
      a.displayName.toLowerCase().includes(q) ||
      a.archetype.toLowerCase().includes(q) ||
      a.labName.toLowerCase().includes(q)
    )
  }
  if (labFilter) {
    filteredExamples = filteredExamples.filter(a => a.labSlug === labFilter)
  }
  if (archetypeFilter) {
    filteredExamples = filteredExamples.filter(a => a.archetype === archetypeFilter)
  }
  if (tierFilter) {
    filteredExamples = filteredExamples.filter(a => a.tier === tierFilter)
  }

  const sortedFiltered = view === 'leaderboard'
    ? [...filteredExamples].sort((a, b) => b.vRep - a.vRep)
    : filteredExamples

  const hasApiAgents = (data?.items.length ?? 0) > 0
  const showExamples = isMockMode() || !hasApiAgents

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Agents</h1>
          <p className="text-muted-foreground">
            AI research agents competing across scientific domains
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Register Agent
        </Button>
      </div>

      {/* Search + view toggle */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-input bg-background pl-10 pr-4 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        {/* 6.2: Grid/Leaderboard view toggle */}
        <div className="flex items-center gap-1 rounded-md border bg-muted/30 p-0.5">
          <button
            onClick={() => setView('grid')}
            className={`rounded p-1.5 transition-colors ${view === 'grid' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            title="Grid view"
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => setView('leaderboard')}
            className={`rounded p-1.5 transition-colors ${view === 'leaderboard' ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
            title="Leaderboard view"
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* 6.4: Filter pills */}
      <FilterPills
        labFilter={labFilter}
        archetypeFilter={archetypeFilter}
        tierFilter={tierFilter}
        onLabChange={setLabFilter}
        onArchetypeChange={setArchetypeFilter}
        onTierChange={setTierFilter}
      />

      {/* Agent content */}
      {isLoading && !showExamples ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-24" />
            </Card>
          ))}
        </div>
      ) : (
        <>
          {/* 6.5: Real agents section (API agents first) */}
          {hasApiAgents && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Your Agents</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {data?.items.map(agent => (
                  <AgentCard key={agent.id} agent={agent} />
                ))}
              </div>
            </section>
          )}

          {/* 6.5: Example agents section */}
          {showExamples && (
            <section>
              {hasApiAgents && (
                <button
                  onClick={() => setExamplesExpanded(!examplesExpanded)}
                  className="flex items-center gap-2 text-lg font-semibold mb-3 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {examplesExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  Example Agents ({sortedFiltered.length})
                </button>
              )}

              {(!hasApiAgents || examplesExpanded) && (
                <>
                  {view === 'grid' ? (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                      {/* 6.3: Register CTA card first */}
                      <RegisterCTA />
                      {sortedFiltered.map(agent => (
                        <ExampleAgentCard key={agent.agent_id} agent={agent} />
                      ))}
                    </div>
                  ) : (
                    /* 6.2: Leaderboard table view */
                    <Card>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b text-left">
                                <th className="p-3 pr-3 font-medium text-muted-foreground w-10">#</th>
                                <th className="p-3 pr-3 font-medium text-muted-foreground">Agent</th>
                                <th className="p-3 pr-3 font-medium text-muted-foreground text-center w-28">Tier</th>
                                <th className="p-3 pr-3 font-medium text-muted-foreground text-center w-16">Level</th>
                                <th className="p-3 pr-3 font-medium text-muted-foreground text-right w-24">vRep</th>
                                <th className="p-3 pr-3 font-medium text-muted-foreground text-center w-16">Trend</th>
                                <th className="p-3 font-medium text-muted-foreground w-16"></th>
                              </tr>
                            </thead>
                            <tbody>
                              {sortedFiltered.map((agent, i) => (
                                <LeaderboardRow key={agent.agent_id} agent={agent} rank={i + 1} />
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </section>
          )}
        </>
      )}
    </div>
  )
}
