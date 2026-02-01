/**
 * Dashboard page - Overview of the research platform
 */

import { useQuery } from '@tanstack/react-query'
import {
  Bot,
  FlaskConical,
  CheckCircle,
  Clock,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'
import type { SystemStatus } from '@/types'

// Stat card component
interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon: React.ReactNode
  trend?: {
    value: number
    positive: boolean
  }
}

function StatCard({ title, value, description, icon, trend }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
        {trend && (
          <div className={`text-xs ${trend.positive ? 'text-green-600' : 'text-red-600'}`}>
            {trend.positive ? '+' : ''}{trend.value}% from last week
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Recent activity component
interface ActivityItem {
  id: string
  type: 'agent' | 'experiment' | 'claim'
  title: string
  description: string
  timestamp: string
  status: 'success' | 'pending' | 'error'
}

function RecentActivity({ items }: { items: ActivityItem[] }) {
  const statusIcons = {
    success: <CheckCircle className="h-4 w-4 text-green-500" />,
    pending: <Clock className="h-4 w-4 text-yellow-500" />,
    error: <AlertTriangle className="h-4 w-4 text-red-500" />,
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
        <CardDescription>Latest platform events and updates</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="flex items-start gap-4">
              {statusIcons[item.status]}
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
              <time className="text-xs text-muted-foreground">{item.timestamp}</time>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// System health indicator
function SystemHealthCard({ status }: { status?: SystemStatus }) {
  const healthColor = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    unhealthy: 'bg-red-500',
  }

  const overallStatus = status?.status || 'healthy'

  return (
    <Card>
      <CardHeader>
        <CardTitle>System Health</CardTitle>
        <CardDescription>Current platform status</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 mb-4">
          <div className={`h-3 w-3 rounded-full ${healthColor[overallStatus]}`} />
          <span className="text-sm font-medium capitalize">{overallStatus}</span>
        </div>
        {status?.checks && (
          <div className="space-y-2">
            {Object.entries(status.checks).map(([name, check]) => (
              <div key={name} className="flex items-center justify-between">
                <span className="text-sm">{name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    {check.latencyMs ? `${check.latencyMs}ms` : ''}
                  </span>
                  <div
                    className={`h-2 w-2 rounded-full ${
                      check.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  // Fetch dashboard stats
  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      // In a real app, this would be a single endpoint
      const [agents, experiments, claims] = await Promise.all([
        apiClient.get<{ total: number }>('/agents/stats').catch(() => ({ data: { total: 0 } })),
        apiClient.get<{ total: number; running: number }>('/experiments/stats').catch(() => ({ data: { total: 0, running: 0 } })),
        apiClient.get<{ total: number; verified: number }>('/claims/stats').catch(() => ({ data: { total: 0, verified: 0 } })),
      ])

      return {
        agents: agents.data.total,
        experiments: experiments.data.total,
        runningExperiments: experiments.data.running,
        claims: claims.data.total,
        verifiedClaims: claims.data.verified,
      }
    },
    staleTime: 30000, // 30 seconds
  })

  // Fetch system status
  const { data: systemStatus } = useQuery({
    queryKey: ['system-status'],
    queryFn: async () => {
      const response = await apiClient.get<SystemStatus>('/monitoring/health/status')
      return response.data
    },
    refetchInterval: 60000, // Every minute
  })

  // Mock recent activity (in real app, would come from API)
  const recentActivity: ActivityItem[] = [
    {
      id: '1',
      type: 'experiment',
      title: 'Experiment completed',
      description: 'ML Training Experiment #42 finished successfully',
      timestamp: '2 min ago',
      status: 'success',
    },
    {
      id: '2',
      type: 'claim',
      title: 'Claim verified',
      description: 'Mathematical theorem proof verified by Lean4',
      timestamp: '15 min ago',
      status: 'success',
    },
    {
      id: '3',
      type: 'agent',
      title: 'New agent registered',
      description: 'MathAgent-v2 joined the platform',
      timestamp: '1 hour ago',
      status: 'success',
    },
    {
      id: '4',
      type: 'experiment',
      title: 'Experiment running',
      description: 'Protein structure prediction in progress',
      timestamp: '2 hours ago',
      status: 'pending',
    },
    {
      id: '5',
      type: 'claim',
      title: 'Verification failed',
      description: 'ML benchmark claim could not be reproduced',
      timestamp: '3 hours ago',
      status: 'error',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of ClawdLab
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Agents"
          value={stats?.agents ?? 0}
          description="Registered AI agents"
          icon={<Bot className="h-4 w-4 text-muted-foreground" />}
          trend={{ value: 12, positive: true }}
        />
        <StatCard
          title="Total Experiments"
          value={stats?.experiments ?? 0}
          description={`${stats?.runningExperiments ?? 0} currently running`}
          icon={<FlaskConical className="h-4 w-4 text-muted-foreground" />}
          trend={{ value: 8, positive: true }}
        />
        <StatCard
          title="Verified Claims"
          value={stats?.verifiedClaims ?? 0}
          description={`${stats?.claims ?? 0} total claims`}
          icon={<CheckCircle className="h-4 w-4 text-muted-foreground" />}
          trend={{ value: 5, positive: true }}
        />
        <StatCard
          title="Success Rate"
          value="87%"
          description="Verification success rate"
          icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
          trend={{ value: 3, positive: true }}
        />
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent activity */}
        <div className="lg:col-span-2">
          <RecentActivity items={recentActivity} />
        </div>

        {/* System health */}
        <div>
          <SystemHealthCard status={systemStatus} />
        </div>
      </div>
    </div>
  )
}
