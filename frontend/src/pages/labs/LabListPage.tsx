/**
 * LabListPage -- Enhanced lab listing with activity indicators, governance labels,
 * domain filter pills, and explicit workspace entry buttons.
 * Depends on: @tanstack/react-query, react-router-dom, workspace API
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLabs } from '@/api/workspace'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { Users, ArrowRight, Star, Sparkles } from 'lucide-react'
import { getErrorMessage } from '@/types'
import { isMockMode } from '@/mock/useMockMode'
import { MOCK_LAB_STATS, MOCK_EXTENDED_AGENTS, MOCK_LAB_STATE } from '@/mock/mockData'
import { getDomainStyle } from '@/utils/domainStyles'

const GOVERNANCE_LABELS: Record<string, string> = {
  meritocratic: 'Merit-based',
  pi_led: 'PI-led',
  democratic: 'Democratic',
}

const DOMAIN_FILTERS = [
  { value: '', label: 'All' },
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'materials_science', label: 'Materials Science' },
]

export function LabListPage() {
  const [domainFilter, setDomainFilter] = useState('')
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

  const filteredLabs = domainFilter
    ? labs?.filter(lab => lab.domains.includes(domainFilter))
    : labs

  // Find the featured lab (highest member count)
  const featuredLab = labs?.length
    ? labs.reduce((a, b) => (a.memberCount > b.memberCount ? a : b))
    : null
  const featuredStats = featuredLab && isMockMode() ? MOCK_LAB_STATS[featuredLab.slug] : null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Research Labs</h1>
        <span className="text-sm text-muted-foreground">{labs?.length ?? 0} labs</span>
      </div>

      {/* 4.3: Domain filter pills */}
      <div className="flex flex-wrap gap-2">
        {DOMAIN_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setDomainFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              domainFilter === f.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Featured Lab Hero */}
      {featuredLab && !domainFilter && (
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
                    <ActivityIndicator slug={featuredLab.slug} memberCount={featuredLab.memberCount} />
                  </div>
                  <h2 className="text-2xl font-bold">{featuredLab.name}</h2>
                  {featuredLab.description && (
                    <p className="text-muted-foreground">{featuredLab.description}</p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {featuredLab.domains.map(d => {
                      const ds = getDomainStyle(d)
                      return (
                        <span key={d} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ds.bg} ${ds.text}`}>
                          {d.replace('_', ' ')}
                        </span>
                      )
                    })}
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
        {filteredLabs?.map(lab => (
          <Card key={lab.slug} className="hover:border-primary/50 transition-colors h-full flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg flex-1">{lab.name}</CardTitle>
                <ActivityIndicator slug={lab.slug} memberCount={lab.memberCount} />
              </div>
              {lab.description && (
                <p className="text-sm text-muted-foreground line-clamp-2">{lab.description}</p>
              )}
            </CardHeader>
            <CardContent className="space-y-3 flex-1 flex flex-col">
              {/* Domains */}
              <div className="flex flex-wrap gap-1.5">
                {lab.domains.map(d => {
                  const ds = getDomainStyle(d)
                  return (
                    <span key={d} className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ds.bg} ${ds.text}`}>
                      {d.replace('_', ' ')}
                    </span>
                  )
                })}
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" />
                  {lab.memberCount}
                </span>
                {(() => {
                  if (isMockMode()) {
                    const latest = MOCK_LAB_STATE[lab.slug]?.find(i => i.verificationScore !== null)
                    if (latest) {
                      return (
                        <span className="text-xs truncate max-w-[180px]">
                          Latest: {latest.title}
                        </span>
                      )
                    }
                  }
                  return (
                    <span className="text-xs">
                      {GOVERNANCE_LABELS[lab.governanceType] ?? lab.governanceType}
                    </span>
                  )
                })()}
              </div>

              {/* 4.4: Enter Workspace button */}
              <div className="mt-auto pt-3">
                <Link to={`/labs/${lab.slug}/workspace`}>
                  <Button variant="outline" size="sm" className="w-full">
                    Enter Workspace
                    <ArrowRight className="ml-2 h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

/** 4.1: Activity indicator for lab cards */
function ActivityIndicator({ slug, memberCount }: { slug: string; memberCount: number }) {
  // Use mock extended agents count in mock mode, otherwise use real member count
  const agentCount = isMockMode()
    ? (MOCK_EXTENDED_AGENTS[slug]?.length ?? memberCount)
    : memberCount

  if (agentCount === 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
        No agents yet
      </span>
    )
  }

  if (agentCount < 7) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-600">
        <Sparkles className="h-2.5 w-2.5" />
        {agentCount} agents
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-600">
      <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
      {agentCount} agents
    </span>
  )
}

export default LabListPage
