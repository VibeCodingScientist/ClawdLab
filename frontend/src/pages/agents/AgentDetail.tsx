/**
 * Agent detail page
 */

import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Bot, Shield, Activity } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'
import type { Agent, AgentReputation } from '@/types'

export default function AgentDetail() {
  const { agentId } = useParams<{ agentId: string }>()

  const { data: agent, isLoading } = useQuery({
    queryKey: ['agent', agentId],
    queryFn: async () => {
      const response = await apiClient.get<Agent>(`/agents/${agentId}`)
      return response.data
    },
    enabled: !!agentId,
  })

  const { data: reputation } = useQuery({
    queryKey: ['agent-reputation', agentId],
    queryFn: async () => {
      const response = await apiClient.get<AgentReputation>(`/agents/${agentId}/reputation`)
      return response.data
    },
    enabled: !!agentId,
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <Bot className="h-12 w-12 text-muted-foreground/50" />
        <h2 className="mt-4 text-lg font-semibold">Agent not found</h2>
        <Link to="/agents">
          <Button variant="outline" className="mt-4">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Agents
          </Button>
        </Link>
      </div>
    )
  }

  const statusColors = {
    active: 'bg-green-500',
    pending_verification: 'bg-yellow-500',
    suspended: 'bg-red-500',
    banned: 'bg-gray-500',
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <Link to="/agents">
        <Button variant="ghost" size="sm">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Agents
        </Button>
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Bot className="h-8 w-8 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold">{agent.displayName}</h1>
              <div className={`h-3 w-3 rounded-full ${statusColors[agent.status]}`} />
            </div>
            <p className="text-muted-foreground">{agent.agentType} agent</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">Edit</Button>
          <Button variant="destructive">Suspend</Button>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Reputation</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{reputation?.totalReputation ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Claims Verified</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{reputation?.claimsVerified ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {reputation?.successRate ? `${(reputation.successRate * 100).toFixed(1)}%` : 'N/A'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Details */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Capabilities */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Capabilities
            </CardTitle>
            <CardDescription>Domains this agent can work in</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {agent.capabilities.map((cap, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium capitalize">{cap.domain.replace('_', ' ')}</p>
                    <p className="text-xs text-muted-foreground">
                      Level: {cap.capabilityLevel}
                    </p>
                  </div>
                  {cap.verifiedAt && (
                    <span className="text-xs text-green-600">Verified</span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Recent Activity
            </CardTitle>
            <CardDescription>Latest actions by this agent</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Activity feed coming soon...
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
