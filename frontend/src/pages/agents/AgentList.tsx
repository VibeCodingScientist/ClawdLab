/**
 * Agent list page
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bot, Plus, Search } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'
import type { Agent, PaginatedResponse } from '@/types'

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Agents</h1>
          <p className="text-muted-foreground">
            Manage and monitor AI research agents
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
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-24" />
            </Card>
          ))}
        </div>
      ) : data?.items.length ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Bot className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No agents found</h3>
            <p className="text-sm text-muted-foreground">
              {search ? 'Try a different search term' : 'Get started by registering your first agent'}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
