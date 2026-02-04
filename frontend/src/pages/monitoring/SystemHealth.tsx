/**
 * System monitoring page
 */

import { useQuery } from '@tanstack/react-query'
import { Activity, Server, Database, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import apiClient from '@/api/client'
import type { SystemStatus, Alert } from '@/types'

export default function SystemHealth() {
  const { data: status } = useQuery({
    queryKey: ['system-status-full'],
    queryFn: async () => {
      const response = await apiClient.get<SystemStatus>('/monitoring/health/status')
      return response.data
    },
    refetchInterval: 30000,
  })

  const healthColor = {
    healthy: 'text-green-500',
    degraded: 'text-yellow-500',
    unhealthy: 'text-red-500',
  }

  const healthBg = {
    healthy: 'bg-green-500/10',
    degraded: 'bg-yellow-500/10',
    unhealthy: 'bg-red-500/10',
  }

  const overallStatus = status?.status || 'healthy'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">System Monitoring</h1>
        <p className="text-muted-foreground">
          Monitor platform health and performance
        </p>
      </div>

      {/* Overall status */}
      <Card className={healthBg[overallStatus]}>
        <CardContent className="flex items-center gap-4 py-4">
          <div className={`rounded-full p-3 ${healthBg[overallStatus]}`}>
            <Activity className={`h-8 w-8 ${healthColor[overallStatus]}`} />
          </div>
          <div>
            <h2 className={`text-2xl font-bold capitalize ${healthColor[overallStatus]}`}>
              System {overallStatus}
            </h2>
            <p className="text-sm text-muted-foreground">
              All services are operating normally
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Service health */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {status?.checks ? (
          Object.entries(status.checks).map(([name, check]) => (
            <Card key={name}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  {name === 'database' && <Database className="h-4 w-4" />}
                  {name === 'redis' && <Server className="h-4 w-4" />}
                  {!['database', 'redis'].includes(name) && <Server className="h-4 w-4" />}
                  {name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${check.status === 'healthy' ? 'text-green-500' : 'text-red-500'}`}>
                    {check.status}
                  </span>
                  {check.latencyMs && (
                    <span className="text-xs text-muted-foreground">
                      {check.latencyMs}ms
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-20" />
            </Card>
          ))
        )}
      </div>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Active Alerts
          </CardTitle>
          <CardDescription>Current system alerts and warnings</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No active alerts
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
