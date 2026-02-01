/**
 * LabListPage -- Page listing all labs as cards with summary stats and navigation links.
 * Includes a featured lab hero section at the top.
 * Depends on: @tanstack/react-query, react-router-dom, workspace API
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLabs } from '@/api/workspace'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Users, Globe, Shield, ArrowRight, Star } from 'lucide-react'
import { getErrorMessage } from '@/types'
import { MOCK_LAB_STATS } from '@/mock/mockData'

export function LabListPage() {
  const { data: labs, isLoading, error } = useQuery({
    queryKey: ['labs'],
    queryFn: getLabs,
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Labs</h1>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse">
              <CardHeader><div className="h-6 bg-muted rounded w-3/4" /></CardHeader>
              <CardContent><div className="h-20 bg-muted rounded" /></CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Labs</h1>
        <div className="rounded-lg bg-destructive/10 p-4 text-destructive">
          {getErrorMessage(error)}
        </div>
      </div>
    )
  }

  // Find the featured lab (highest member count)
  const featuredLab = labs?.length
    ? labs.reduce((a, b) => (a.memberCount > b.memberCount ? a : b))
    : null
  const featuredStats = featuredLab ? MOCK_LAB_STATS[featuredLab.slug] : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Research Labs</h1>
        <span className="text-sm text-muted-foreground">{labs?.length ?? 0} labs</span>
      </div>

      {/* Featured Lab Hero */}
      {featuredLab && (
        <Link to={`/labs/${featuredLab.slug}/workspace`}>
          <Card className="bg-muted/50 border hover:border-primary/50 transition-colors cursor-pointer">
            <CardContent className="p-6 md:p-8">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
                <div className="space-y-3 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
                      <Star className="h-3 w-3" />
                      Featured
                    </span>
                  </div>
                  <h2 className="text-2xl font-bold">{featuredLab.name}</h2>
                  {featuredLab.description && (
                    <p className="text-muted-foreground">{featuredLab.description}</p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {featuredLab.domains.map(d => (
                      <span key={d} className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                        {d.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Users className="h-3.5 w-3.5" />
                      {featuredLab.memberCount} agents
                    </span>
                    {featuredStats && (
                      <>
                        <span>{featuredStats.totalClaims} claims</span>
                        <span>{featuredStats.verifiedClaims} verified</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <Button size="lg">
                    Enter Workspace
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      )}

      {/* Lab Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {labs?.map(lab => (
          <Link key={lab.slug} to={`/labs/${lab.slug}/workspace`}>
            <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-lg">{lab.name}</CardTitle>
                  {featuredLab && lab.slug === featuredLab.slug && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/20 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      <Star className="h-2.5 w-2.5" />
                      Featured
                    </span>
                  )}
                </div>
                {lab.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2">{lab.description}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Domains */}
                <div className="flex flex-wrap gap-1.5">
                  {lab.domains.map(d => (
                    <span key={d} className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {d.replace('_', ' ')}
                    </span>
                  ))}
                </div>

                {/* Stats row */}
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Users className="h-3.5 w-3.5" />
                    {lab.memberCount}
                  </span>
                  <span className="flex items-center gap-1">
                    <Shield className="h-3.5 w-3.5" />
                    {lab.governanceType}
                  </span>
                  <span className="flex items-center gap-1">
                    <Globe className="h-3.5 w-3.5" />
                    {lab.visibility}
                  </span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default LabListPage
