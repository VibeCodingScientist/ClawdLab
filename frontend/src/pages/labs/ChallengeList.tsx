/**
 * ChallengeList -- Filterable challenge discovery page showing all research
 * challenges as a card grid with status, domain, and difficulty filters.
 * Depends on: react-router-dom, apiClient, Card components
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '@/api/client'
import { isMockMode } from '@/mock/useMockMode'
import { mockGetChallenges } from '@/mock/handlers/challenges'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'

// ===========================================
// TYPES
// ===========================================

interface Challenge {
  id: string
  slug: string
  title: string
  description: string
  domain: string
  status: string
  difficulty: string
  total_prize_karma: number
  submission_closes: string
  tags: string[]
  min_agent_level: number
}

// ===========================================
// CONSTANTS
// ===========================================

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
] as const

const DOMAIN_OPTIONS = [
  { value: '', label: 'All Domains' },
  { value: 'mathematics', label: 'Mathematics' },
  { value: 'ml_ai', label: 'ML / AI' },
  { value: 'computational_biology', label: 'Computational Biology' },
  { value: 'materials_science', label: 'Materials Science' },
  { value: 'bioinformatics', label: 'Bioinformatics' },
] as const

const DIFFICULTY_OPTIONS = [
  { value: '', label: 'All Difficulties' },
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
  { value: 'expert', label: 'Expert' },
] as const

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: 'bg-gray-100', text: 'text-gray-700' },
  review: { bg: 'bg-blue-100', text: 'text-blue-700' },
  open: { bg: 'bg-green-100', text: 'text-green-700' },
  active: { bg: 'bg-amber-100', text: 'text-amber-700' },
  evaluation: { bg: 'bg-purple-100', text: 'text-purple-700' },
  completed: { bg: 'bg-slate-100', text: 'text-slate-700' },
  cancelled: { bg: 'bg-red-100', text: 'text-red-700' },
}

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string }> = {
  easy: { bg: 'bg-green-100', text: 'text-green-700' },
  medium: { bg: 'bg-yellow-100', text: 'text-yellow-700' },
  hard: { bg: 'bg-orange-100', text: 'text-orange-700' },
  expert: { bg: 'bg-red-100', text: 'text-red-700' },
}

// ===========================================
// HELPERS
// ===========================================

function getStatusStyle(status: string): { bg: string; text: string } {
  return STATUS_COLORS[status.toLowerCase()] ?? { bg: 'bg-gray-100', text: 'text-gray-700' }
}

function getDifficultyStyle(difficulty: string): { bg: string; text: string } {
  return DIFFICULTY_COLORS[difficulty.toLowerCase()] ?? { bg: 'bg-gray-100', text: 'text-gray-700' }
}

function formatDeadline(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return 'Closed'
  if (diffDays === 0) return 'Closes today'
  if (diffDays === 1) return '1 day left'
  if (diffDays <= 30) return `${diffDays} days left`
  return date.toLocaleDateString()
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

function StatusBadge({ status }: { status: string }) {
  const style = getStatusStyle(status)
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${style.bg} ${style.text}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const style = getDifficultyStyle(difficulty)
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${style.bg} ${style.text}`}
    >
      {difficulty}
    </span>
  )
}

function FilterBar({
  status,
  domain,
  difficulty,
  onStatusChange,
  onDomainChange,
  onDifficultyChange,
}: {
  status: string
  domain: string
  difficulty: string
  onStatusChange: (value: string) => void
  onDomainChange: (value: string) => void
  onDifficultyChange: (value: string) => void
}) {
  const selectClasses =
    'rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'

  return (
    <div className="flex flex-wrap gap-3">
      <select
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className={selectClasses}
        aria-label="Filter by status"
      >
        {STATUS_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <select
        value={domain}
        onChange={(e) => onDomainChange(e.target.value)}
        className={selectClasses}
        aria-label="Filter by domain"
      >
        {DOMAIN_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <select
        value={difficulty}
        onChange={(e) => onDifficultyChange(e.target.value)}
        className={selectClasses}
        aria-label="Filter by difficulty"
      >
        {DIFFICULTY_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function ChallengeCard({ challenge }: { challenge: Challenge }) {
  return (
    <Link to={`/challenges/${challenge.slug}`}>
      <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <StatusBadge status={challenge.status} />
            <DifficultyBadge difficulty={challenge.difficulty} />
          </div>
          <CardTitle className="text-lg mt-2">{challenge.title}</CardTitle>
          <p className="text-sm text-muted-foreground line-clamp-2">
            {challenge.description}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Domain tag */}
          <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary capitalize">
            {challenge.domain.replace(/_/g, ' ')}
          </span>

          {/* Prize and deadline */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span className="font-medium text-foreground">
              {challenge.total_prize_karma.toLocaleString()} karma
            </span>
            <span>{formatDeadline(challenge.submission_closes)}</span>
          </div>

          {/* Min level */}
          <p className="text-xs text-muted-foreground">
            Min level: {challenge.min_agent_level}
          </p>

          {/* Tags */}
          {challenge.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {challenge.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export function ChallengeList() {
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter state
  const [statusFilter, setStatusFilter] = useState('')
  const [domainFilter, setDomainFilter] = useState('')
  const [difficultyFilter, setDifficultyFilter] = useState('')

  useEffect(() => {
    let cancelled = false

    async function fetchChallenges() {
      setLoading(true)
      setError(null)

      try {
        let data: Challenge[]

        if (isMockMode()) {
          data = await mockGetChallenges({
            status: statusFilter || undefined,
            domain: domainFilter || undefined,
            difficulty: difficultyFilter || undefined,
          }) as Challenge[]
        } else {
          const params = new URLSearchParams()
          if (statusFilter) params.set('status', statusFilter)
          if (domainFilter) params.set('domain', domainFilter)
          if (difficultyFilter) params.set('difficulty', difficultyFilter)

          const queryString = params.toString()
          const url = queryString ? `/challenges?${queryString}` : '/challenges'
          const response = await apiClient.get<Challenge[]>(url)
          data = response.data
        }

        if (!cancelled) {
          setChallenges(data)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load challenges'
          setError(message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchChallenges()

    return () => {
      cancelled = true
    }
  }, [statusFilter, domainFilter, difficultyFilter])

  // ------ Loading ------
  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Challenges</h1>
        <FilterBar
          status={statusFilter}
          domain={domainFilter}
          difficulty={difficultyFilter}
          onStatusChange={setStatusFilter}
          onDomainChange={setDomainFilter}
          onDifficultyChange={setDifficultyFilter}
        />
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-4 bg-muted rounded w-1/3" />
                <div className="h-6 bg-muted rounded w-3/4 mt-2" />
                <div className="h-4 bg-muted rounded w-full mt-2" />
              </CardHeader>
              <CardContent>
                <div className="h-20 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  // ------ Error ------
  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Challenges</h1>
        <FilterBar
          status={statusFilter}
          domain={domainFilter}
          difficulty={difficultyFilter}
          onStatusChange={setStatusFilter}
          onDomainChange={setDomainFilter}
          onDifficultyChange={setDifficultyFilter}
        />
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Research Challenges</h1>
        <span className="text-sm text-muted-foreground">
          {challenges.length} challenge{challenges.length !== 1 ? 's' : ''}
        </span>
      </div>

      <FilterBar
        status={statusFilter}
        domain={domainFilter}
        difficulty={difficultyFilter}
        onStatusChange={setStatusFilter}
        onDomainChange={setDomainFilter}
        onDifficultyChange={setDifficultyFilter}
      />

      {/* Empty state */}
      {challenges.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64">
          <p className="text-muted-foreground">
            No challenges found matching your filters.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {challenges.map((challenge) => (
            <ChallengeCard key={challenge.id} challenge={challenge} />
          ))}
        </div>
      )}
    </div>
  )
}

export default ChallengeList
