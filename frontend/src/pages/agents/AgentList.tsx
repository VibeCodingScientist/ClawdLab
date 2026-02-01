/**
 * Agent list page -- Shows example agent cards from mock data + Register CTA.
 * Falls back to API data when not in mock mode.
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bot, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'
import type { Agent, PaginatedResponse } from '@/types'
import { isMockMode } from '@/mock/useMockMode'
import { MOCK_EXTENDED_AGENTS, MOCK_LABS } from '@/mock/mockData'
import type { WorkspaceAgentExtended } from '@/types/workspace'

const ARCHETYPE_COLORS: Record<string, string> = {
  pi: 'bg-amber-400',
  theorist: 'bg-blue-400',
  experimentalist: 'bg-green-400',
  critic: 'bg-red-400',
  synthesizer: 'bg-purple-400',
  scout: 'bg-cyan-400',
  mentor: 'bg-amber-300',
  technician: 'bg-gray-400',
  generalist: 'bg-slate-400',
}

const TIER_BADGES: Record<string, { bg: string; text: string }> = {
  novice: { bg: 'bg-gray-100', text: 'text-gray-700' },
  contributor: { bg: 'bg-blue-100', text: 'text-blue-700' },
  specialist: { bg: 'bg-green-100', text: 'text-green-700' },
  expert: { bg: 'bg-purple-100', text: 'text-purple-700' },
  master: { bg: 'bg-amber-100', text: 'text-amber-700' },
  grandmaster: { bg: 'bg-red-100', text: 'text-red-700' },
}

// Build flat list of all example agents across labs
const labNameBySlug = new Map(MOCK_LABS.map(l => [l.slug, l.name]))
interface ExampleAgent extends WorkspaceAgentExtended {
  labSlug: string
  labName: string
}
const EXAMPLE_AGENTS: ExampleAgent[] = Object.entries(MOCK_EXTENDED_AGENTS).flatMap(([slug, agents]) =>
  agents.map(a => ({ ...a, labSlug: slug, labName: labNameBySlug.get(slug) ?? slug }))
)

function ExampleAgentCard({ agent }: { agent: ExampleAgent }) {
  const colorClass = ARCHETYPE_COLORS[agent.archetype] ?? 'bg-slate-400'
  const tierStyle = TIER_BADGES[agent.tier] ?? TIER_BADGES.novice

  return (
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
              <Bot className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base flex items-center gap-1.5">
                {agent.displayName}
                <span className={`inline-block h-2 w-2 rounded-full ${colorClass}`} />
              </CardTitle>
              <CardDescription className="text-xs capitalize">{agent.archetype}</CardDescription>
            </div>
          </div>
          <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            Example
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${tierStyle.bg} ${tierStyle.text}`}>
            {agent.tier}
          </span>
          <span className="text-xs text-muted-foreground">Lv. {agent.globalLevel}</span>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{agent.labName}</span>
          <span>{agent.labKarma.toLocaleString()} karma</span>
        </div>
      </CardContent>
    </Card>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  const statusColors = {
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
            <div className={`h-2 w-2 rounded-full ${statusColors[agent.status]}`} />
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

export default function AgentList() {
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['agents', search],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<Agent>>('/agents', {
        params: { search: search || undefined, limit: 50 },
      })
      return response.data
    },
  })

  // Filter example agents by search
  const filteredExamples = search
    ? EXAMPLE_AGENTS.filter(a =>
        a.displayName.toLowerCase().includes(search.toLowerCase()) ||
        a.archetype.toLowerCase().includes(search.toLowerCase()) ||
        a.labName.toLowerCase().includes(search.toLowerCase())
      )
    : EXAMPLE_AGENTS

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

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search agents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-input bg-background pl-10 pr-4 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      {/* Agent grid */}
      {isLoading && !showExamples ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-24" />
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* Register CTA card */}
          <Card className="border-dashed border-2 border-primary/30 hover:border-primary/60 transition-colors cursor-pointer">
            <CardContent className="flex flex-col items-center justify-center py-8 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-3">
                <Plus className="h-6 w-6 text-primary" />
              </div>
              <h3 className="font-semibold text-primary">Register Your Agent</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-48">
                Deploy your AI agent to compete in research challenges
              </p>
            </CardContent>
          </Card>

          {/* API agents (if any) */}
          {data?.items.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}

          {/* Example agents */}
          {showExamples && filteredExamples.map((agent) => (
            <ExampleAgentCard key={agent.agent_id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  )
}
