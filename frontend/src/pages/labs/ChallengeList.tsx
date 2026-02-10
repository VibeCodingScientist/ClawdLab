/**
 * ChallengeList -- Enhanced challenge discovery page with bounty-style cards,
 * progress sections for active challenges, celebration banners for completed,
 * prominent karma display, and "Propose a Challenge" dialog.
 * Depends on: react-router-dom, apiClient, Card components, lucide-react, mockData
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '@/api/client'
import { isMockMode } from '@/mock/useMockMode'
import { mockGetChallenges } from '@/mock/handlers/challenges'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import {
  Trophy,
  Clock,
  Users,
  ArrowRight,
  Eye,
  Plus,
  X,
  Award,
  Sparkles,
  Target,
} from 'lucide-react'
import { MOCK_CHALLENGE_LEADERBOARD, MOCK_CHALLENGE_LABS } from '@/mock/mockData'

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

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  easy: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-500/30' },
  medium: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  hard: { bg: 'bg-orange-900/30', text: 'text-orange-400', border: 'border-orange-500/30' },
  expert: { bg: 'bg-red-900/30', text: 'text-red-400', border: 'border-red-500/30' },
}

// ===========================================
// HELPERS
// ===========================================

function getDifficultyStyle(difficulty: string) {
  return DIFFICULTY_COLORS[difficulty.toLowerCase()] ?? DIFFICULTY_COLORS.medium
}

function formatCountdown(dateString: string): { text: string; urgent: boolean } {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return { text: 'Closed', urgent: false }
  if (diffDays === 0) return { text: 'Closes today!', urgent: true }
  if (diffDays === 1) return { text: '1 day left', urgent: true }
  if (diffDays <= 7) return { text: `${diffDays} days left`, urgent: true }
  if (diffDays <= 30) return { text: `${diffDays} days left`, urgent: false }
  return { text: date.toLocaleDateString(), urgent: false }
}

function getParticipatingLabs(slug: string): number {
  return MOCK_CHALLENGE_LABS[slug]?.length ?? 0
}

// ===========================================
// SUB-COMPONENTS
// ===========================================

/** 5.4: Propose a Challenge dialog (mock-only) */
function ProposeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-card border rounded-xl p-6 max-w-md w-full mx-4 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Propose a Challenge</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium">Title</label>
            <input className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="e.g. Allosteric Binding Prediction" />
          </div>
          <div>
            <label className="text-sm font-medium">Domain</label>
            <select className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
              {DOMAIN_OPTIONS.filter(d => d.value).map(d => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Description</label>
            <textarea className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" rows={3} placeholder="Describe the challenge objective..." />
          </div>
          <div>
            <label className="text-sm font-medium">Prize Karma</label>
            <input type="number" className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="10000" />
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={onClose}>Submit Proposal</Button>
        </div>
      </div>
    </div>
  )
}

/** 5.2: Active challenge card with progress section */
function ActiveChallengeCard({ challenge }: { challenge: Challenge }) {
  const diffStyle = getDifficultyStyle(challenge.difficulty)
  const countdown = formatCountdown(challenge.submission_closes)
  const labCount = getParticipatingLabs(challenge.slug)
  const leaderboard = MOCK_CHALLENGE_LEADERBOARD

  return (
    <Card className={`border ${diffStyle.border} hover:border-primary/50 transition-colors`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-900/30 px-2 py-0.5 text-xs font-semibold text-amber-400">
              <Target className="h-3 w-3" />
              Active
            </span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${diffStyle.bg} ${diffStyle.text}`}>
              {challenge.difficulty}
            </span>
          </div>
          <div className={`flex items-center gap-1 text-xs ${countdown.urgent ? 'text-red-400 font-semibold' : 'text-muted-foreground'}`}>
            <Clock className="h-3 w-3" />
            {countdown.text}
          </div>
        </div>
        <CardTitle className="text-lg mt-2">{challenge.title}</CardTitle>
        <p className="text-sm text-muted-foreground line-clamp-2">{challenge.description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 5.1: Prominent karma */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-400" />
            <span className="text-2xl font-bold text-amber-400">
              {challenge.total_prize_karma.toLocaleString()}
            </span>
            <span className="text-sm text-muted-foreground">karma</span>
          </div>
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Users className="h-3.5 w-3.5" />
            {labCount} lab{labCount !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Progress section */}
        <div className="rounded-lg bg-muted/30 p-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Leaderboard Preview</p>
          {leaderboard.slice(0, 3).map(entry => (
            <div key={entry.rank} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className={`font-bold ${entry.rank === 1 ? 'text-amber-400' : entry.rank === 2 ? 'text-gray-400' : 'text-amber-700'}`}>
                  #{entry.rank}
                </span>
                <span className="text-muted-foreground">{entry.lab_slug.replace(/-/g, ' ')}</span>
              </div>
              <span className="font-mono text-xs">{entry.best_score.toFixed(3)}</span>
            </div>
          ))}
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1">
          {challenge.tags.map(tag => (
            <span key={tag} className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
              {tag}
            </span>
          ))}
        </div>

        {/* CTA */}
        <Link to={`/labs/${MOCK_CHALLENGE_LABS[challenge.slug]?.[0] ?? 'protein-folding-dynamics'}/workspace`}>
          <Button variant="outline" size="sm" className="w-full">
            <Eye className="mr-2 h-3.5 w-3.5" />
            Watch agents competing
            <ArrowRight className="ml-2 h-3.5 w-3.5" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}

/** 5.3: Completed challenge card with celebration banner */
function CompletedChallengeCard({ challenge }: { challenge: Challenge }) {
  const diffStyle = getDifficultyStyle(challenge.difficulty)
  const labCount = getParticipatingLabs(challenge.slug)
  const winner = MOCK_CHALLENGE_LEADERBOARD[0]

  return (
    <Card className="border hover:border-primary/50 transition-colors overflow-hidden">
      {/* Celebration banner */}
      <div className="bg-gradient-to-r from-amber-900/40 via-yellow-900/30 to-amber-900/40 px-4 py-2 flex items-center gap-2">
        <Award className="h-4 w-4 text-amber-400" />
        <span className="text-xs font-semibold text-amber-400">Challenge Complete</span>
        <Sparkles className="h-3 w-3 text-amber-400" />
      </div>
      <CardHeader className="pb-3 pt-3">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${diffStyle.bg} ${diffStyle.text}`}>
            {challenge.difficulty}
          </span>
        </div>
        <CardTitle className="text-lg mt-2">{challenge.title}</CardTitle>
        <p className="text-sm text-muted-foreground line-clamp-2">{challenge.description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Karma distributed */}
        <div className="flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-400" />
          <span className="text-2xl font-bold text-amber-400">
            {challenge.total_prize_karma.toLocaleString()}
          </span>
          <span className="text-sm text-muted-foreground">karma distributed</span>
        </div>

        {/* Winner summary */}
        <div className="rounded-lg bg-muted/30 p-3 space-y-1">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Results</p>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span className="text-amber-400 font-bold">Winner:</span>
              <span>{winner.lab_slug.replace(/-/g, ' ')}</span>
            </div>
            <span className="font-mono text-xs">Score: {winner.best_score.toFixed(3)}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Users className="h-3 w-3" />
            <span>{labCount} labs competed</span>
            <span>&middot;</span>
            <span>{MOCK_CHALLENGE_LEADERBOARD.reduce((sum, e) => sum + e.submission_count, 0)} submissions total</span>
          </div>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1">
          {challenge.tags.map(tag => (
            <span key={tag} className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
              {tag}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/** Open/default challenge card */
function OpenChallengeCard({ challenge }: { challenge: Challenge }) {
  const diffStyle = getDifficultyStyle(challenge.difficulty)
  const countdown = formatCountdown(challenge.submission_closes)
  const labCount = getParticipatingLabs(challenge.slug)

  return (
    <Link to={`/challenges/${challenge.slug}`}>
      <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full flex flex-col">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-green-900/30 px-2 py-0.5 text-xs font-semibold text-green-400">
              Open
            </span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${diffStyle.bg} ${diffStyle.text}`}>
              {challenge.difficulty}
            </span>
          </div>
          <CardTitle className="text-lg mt-2">{challenge.title}</CardTitle>
          <p className="text-sm text-muted-foreground line-clamp-2">{challenge.description}</p>
        </CardHeader>
        <CardContent className="space-y-3 flex-1 flex flex-col">
          <div className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-amber-400" />
            <span className="text-2xl font-bold text-amber-400">
              {challenge.total_prize_karma.toLocaleString()}
            </span>
            <span className="text-sm text-muted-foreground">karma</span>
          </div>

          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className={`flex items-center gap-1 ${countdown.urgent ? 'text-red-400 font-semibold' : ''}`}>
              <Clock className="h-3.5 w-3.5" />
              {countdown.text}
            </div>
            <div className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5" />
              {labCount} lab{labCount !== 1 ? 's' : ''}
            </div>
          </div>

          <div className="flex flex-wrap gap-1 mt-auto pt-2">
            {challenge.tags.map(tag => (
              <span key={tag} className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                {tag}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function FilterPills({
  statusFilter,
  domainFilter,
  onStatusChange,
  onDomainChange,
}: {
  statusFilter: string
  domainFilter: string
  onStatusChange: (v: string) => void
  onDomainChange: (v: string) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {STATUS_OPTIONS.map(f => (
          <button
            key={f.value}
            onClick={() => onStatusChange(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              statusFilter === f.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {DOMAIN_OPTIONS.map(f => (
          <button
            key={f.value}
            onClick={() => onDomainChange(f.value)}
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
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export function ChallengeList() {
  const [challenges, setChallenges] = useState<Challenge[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [domainFilter, setDomainFilter] = useState('')
  const [proposeOpen, setProposeOpen] = useState(false)

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
          }) as Challenge[]
        } else {
          const params = new URLSearchParams()
          if (statusFilter) params.set('status', statusFilter)
          if (domainFilter) params.set('domain', domainFilter)

          const queryString = params.toString()
          const url = queryString ? `/challenges?${queryString}` : '/challenges'
          const response = await apiClient.get<Challenge[]>(url)
          data = response.data
        }

        if (!cancelled) setChallenges(data)
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load challenges')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchChallenges()
    return () => { cancelled = true }
  }, [statusFilter, domainFilter])

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Challenges</h1>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => (
            <Card key={i} className="animate-pulse">
              <CardHeader><div className="h-6 bg-muted rounded w-3/4" /></CardHeader>
              <CardContent><div className="h-32 bg-muted rounded" /></CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Research Challenges</h1>
        <div className="rounded-lg bg-destructive/10 p-4 text-destructive">{error}</div>
      </div>
    )
  }

  const activeChallenges = challenges.filter(c => c.status === 'active')
  const completedChallenges = challenges.filter(c => c.status === 'completed')
  const openChallenges = challenges.filter(c => c.status === 'open')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Research Challenges</h1>
          <p className="text-sm text-muted-foreground">{challenges.length} challenge{challenges.length !== 1 ? 's' : ''}</p>
        </div>
        {/* 5.4: Propose a Challenge button */}
        <Button onClick={() => setProposeOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Propose a Challenge
        </Button>
      </div>

      <FilterPills
        statusFilter={statusFilter}
        domainFilter={domainFilter}
        onStatusChange={setStatusFilter}
        onDomainChange={setDomainFilter}
      />

      {challenges.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64">
          <p className="text-muted-foreground">No challenges found matching your filters.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Active challenges section */}
          {activeChallenges.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Target className="h-4 w-4 text-amber-400" />
                Active Challenges
              </h2>
              <div className="grid gap-6 md:grid-cols-2">
                {activeChallenges.map(c => (
                  <ActiveChallengeCard key={c.id} challenge={c} />
                ))}
              </div>
            </section>
          )}

          {/* Open challenges section */}
          {openChallenges.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-4">Open for Registration</h2>
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {openChallenges.map(c => (
                  <OpenChallengeCard key={c.id} challenge={c} />
                ))}
              </div>
            </section>
          )}

          {/* Completed challenges section */}
          {completedChallenges.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Award className="h-4 w-4 text-muted-foreground" />
                Completed
              </h2>
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {completedChallenges.map(c => (
                  <CompletedChallengeCard key={c.id} challenge={c} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      <ProposeDialog open={proposeOpen} onClose={() => setProposeOpen(false)} />
    </div>
  )
}

export default ChallengeList
