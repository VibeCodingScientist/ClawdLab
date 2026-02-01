/**
 * LabOverview -- Lab detail card showing stats, members, and "Open Workspace" navigation.
 * Depends on: @tanstack/react-query, workspace/observatory APIs, ARCHETYPE_CONFIGS
 */
import { useQuery } from '@tanstack/react-query'
import { getLabDetail, getLabStats } from '@/api/workspace'
import { getLabImpact } from '@/api/observatory'
import { ARCHETYPE_CONFIGS, type RoleArchetype } from '@/workspace/game/config/archetypes'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Users, Award, BookOpen, Quote, ArrowRight } from 'lucide-react'
import { getErrorMessage } from '@/types'

interface LabOverviewProps {
  slug: string
  onOpenWorkspace: () => void
}

export function LabOverview({ slug, onOpenWorkspace }: LabOverviewProps) {
  const { data: detail, isLoading: detailLoading, error: detailError } = useQuery({
    queryKey: ['lab-detail', slug],
    queryFn: () => getLabDetail(slug),
  })

  const { data: stats } = useQuery({
    queryKey: ['lab-stats', slug],
    queryFn: () => getLabStats(slug),
    enabled: !!slug,
  })

  const { data: impact } = useQuery({
    queryKey: ['lab-impact', slug],
    queryFn: () => getLabImpact(slug),
    enabled: !!slug,
  })

  if (detailLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (detailError || !detail) {
    return (
      <div className="p-6 text-destructive">
        {detailError ? getErrorMessage(detailError) : 'Lab not found'}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">{detail.name}</h2>
          {detail.description && (
            <p className="text-muted-foreground mt-1">{detail.description}</p>
          )}
          <div className="flex gap-2 mt-3">
            {detail.domains.map(d => (
              <span key={d} className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
                {d.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
        <Button onClick={onOpenWorkspace} className="gap-2">
          Open Workspace
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Users className="h-3.5 w-3.5" /> Members
            </div>
            <p className="text-2xl font-bold">{detail.memberCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Award className="h-3.5 w-3.5" /> Verified Claims
            </div>
            <p className="text-2xl font-bold">{stats?.verifiedClaims ?? '—'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <BookOpen className="h-3.5 w-3.5" /> h-index
            </div>
            <p className="text-2xl font-bold">{impact?.h_index ?? stats?.hIndex ?? '—'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
              <Quote className="h-3.5 w-3.5" /> Citations
            </div>
            <p className="text-2xl font-bold">{impact?.citations_received ?? stats?.citationsReceived ?? '—'}</p>
          </CardContent>
        </Card>
      </div>

      {/* Open Roles */}
      {detail.openRoles && detail.openRoles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Open Roles</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {detail.openRoles.map(role => {
                const config = ARCHETYPE_CONFIGS[role as RoleArchetype]
                return (
                  <span
                    key={role}
                    className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium border"
                    style={{
                      borderColor: config?.color ?? '#888',
                      color: config?.color ?? '#888',
                    }}
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: config?.color ?? '#888' }}
                    />
                    {config?.label ?? role}
                  </span>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Governance & Visibility */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>Governance: <span className="text-foreground font-medium">{detail.governanceType}</span></span>
        <span>Visibility: <span className="text-foreground font-medium">{detail.visibility}</span></span>
        <span>Created: <span className="text-foreground font-medium">{new Date(detail.createdAt).toLocaleDateString()}</span></span>
      </div>
    </div>
  )
}
