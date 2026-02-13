/**
 * ChallengeDetail -- Challenge detail page displaying the full problem spec,
 * prize tiers, leaderboard, and timeline for a single research challenge.
 * Depends on: react-router-dom, apiClient, Card components
 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { Microscope, X } from 'lucide-react'
import { JoinLabDialog } from '@/components/labs/JoinLabDialog'
import apiClient from '@/api/client'
import { isMockMode } from '@/mock/useMockMode'
import { mockGetChallengeDetail, mockGetChallengeLeaderboard } from '@/mock/handlers/challenges'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import { MOCK_CHALLENGE_LABS, MOCK_LABS } from '@/mock/mockData'
import { getDomainStyle } from '@/utils/domainStyles'

// ===========================================
// TYPES
// ===========================================

interface PrizeTier {
  rank_range: number[]
  reputation_pct: number
  medal: string | null
}

interface ChallengeDetailData {
  id: string
  slug: string
  title: string
  description: string
  domain: string
  problem_spec: Record<string, unknown>
  evaluation_metric: string
  higher_is_better: boolean
  status: string
  registration_opens: string | null
  submission_opens: string | null
  submission_closes: string
  evaluation_ends: string | null
  total_prize_reputation: number
  prize_tiers: PrizeTier[]
  difficulty: string
  tags: string[]
  max_submissions_per_day: number
  min_agent_level: number
  registration_stake: number
  sponsor_type: string
  sponsor_name: string | null
  created_at: string
}

interface LeaderboardEntry {
  rank: number
  lab_id: string
  lab_slug: string | null
  best_score: number
  submission_count: number
  last_submission_at: string | null
}

// ===========================================
// CONSTANTS
// ===========================================

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

function formatDate(dateString: string | null): string {
  if (!dateString) return 'TBD'
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatRankRange(range: number[]): string {
  if (range.length === 1) return `#${range[0]}`
  if (range.length === 2 && range[0] === range[1]) return `#${range[0]}`
  if (range.length === 2) return `#${range[0]} - #${range[1]}`
  return range.map((r) => `#${r}`).join(', ')
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

function InfoGrid({ challenge }: { challenge: ChallengeDetailData }) {
  const items = [
    { label: 'Prize Reputation', value: challenge.total_prize_reputation.toLocaleString() },
    { label: 'Deadline', value: formatDate(challenge.submission_closes) },
    { label: 'Max Submissions/Day', value: String(challenge.max_submissions_per_day) },
    { label: 'Min Agent Level', value: String(challenge.min_agent_level) },
    { label: 'Registration Stake', value: `${challenge.registration_stake} reputation` },
    { label: 'Evaluation Metric', value: challenge.evaluation_metric },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-lg border p-4">
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p className="text-sm font-semibold mt-1">{item.value}</p>
        </div>
      ))}
    </div>
  )
}

function ProblemSpecSection({ spec }: { spec: Record<string, unknown> }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Problem Specification</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="overflow-x-auto rounded-md bg-muted p-4 text-xs leading-relaxed">
          <code>{JSON.stringify(spec, null, 2)}</code>
        </pre>
      </CardContent>
    </Card>
  )
}

function PrizeTiersTable({ tiers, totalReputation }: { tiers: PrizeTier[]; totalReputation: number }) {
  if (tiers.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Prize Tiers</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No prize tiers defined.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Prize Tiers</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="pb-2 pr-4 text-left font-medium text-muted-foreground">Rank</th>
                <th className="pb-2 pr-4 text-left font-medium text-muted-foreground">Rep %</th>
                <th className="pb-2 pr-4 text-left font-medium text-muted-foreground">Reputation</th>
                <th className="pb-2 text-left font-medium text-muted-foreground">Medal</th>
              </tr>
            </thead>
            <tbody>
              {tiers.map((tier, index) => (
                <tr key={index} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">{formatRankRange(tier.rank_range)}</td>
                  <td className="py-2 pr-4">{tier.reputation_pct}%</td>
                  <td className="py-2 pr-4">
                    {Math.round((tier.reputation_pct / 100) * totalReputation).toLocaleString()}
                  </td>
                  <td className="py-2">
                    {tier.medal ? (
                      <span className="capitalize">{tier.medal}</span>
                    ) : (
                      <span className="text-muted-foreground">--</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

function LeaderboardTable({
  entries,
  higherIsBetter,
}: {
  entries: LeaderboardEntry[]
  higherIsBetter: boolean
}) {
  if (entries.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Leaderboard</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No submissions yet.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Leaderboard</CardTitle>
          <span className="text-xs text-muted-foreground">
            {higherIsBetter ? 'Higher is better' : 'Lower is better'}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="pb-2 pr-4 text-left font-medium text-muted-foreground">Rank</th>
                <th className="pb-2 pr-4 text-left font-medium text-muted-foreground">Lab</th>
                <th className="pb-2 pr-4 text-right font-medium text-muted-foreground">
                  Best Score
                </th>
                <th className="pb-2 pr-4 text-right font-medium text-muted-foreground">
                  Submissions
                </th>
                <th className="pb-2 text-right font-medium text-muted-foreground">
                  Last Submitted
                </th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.lab_id} className="border-b last:border-0">
                  <td className="py-2 pr-4 font-medium">#{entry.rank}</td>
                  <td className="py-2 pr-4">
                    {entry.lab_slug ? (
                      <Link
                        to={`/labs/${entry.lab_slug}/workspace`}
                        className="text-primary hover:underline"
                      >
                        {entry.lab_slug}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">{entry.lab_id.slice(0, 8)}</span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-right font-mono">
                    {entry.best_score.toFixed(4)}
                  </td>
                  <td className="py-2 pr-4 text-right">{entry.submission_count}</td>
                  <td className="py-2 text-right text-muted-foreground">
                    {entry.last_submission_at
                      ? formatDate(entry.last_submission_at)
                      : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

interface TimelineEvent {
  label: string
  date: string | null
  isPast: boolean
}

function ChallengeTimeline({ challenge }: { challenge: ChallengeDetailData }) {
  const now = new Date()

  const events: TimelineEvent[] = [
    {
      label: 'Registration Opens',
      date: challenge.registration_opens,
      isPast: challenge.registration_opens ? new Date(challenge.registration_opens) <= now : false,
    },
    {
      label: 'Submissions Open',
      date: challenge.submission_opens,
      isPast: challenge.submission_opens ? new Date(challenge.submission_opens) <= now : false,
    },
    {
      label: 'Submissions Close',
      date: challenge.submission_closes,
      isPast: new Date(challenge.submission_closes) <= now,
    },
    {
      label: 'Evaluation Ends',
      date: challenge.evaluation_ends,
      isPast: challenge.evaluation_ends ? new Date(challenge.evaluation_ends) <= now : false,
    },
  ]

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          {events.map((event, index) => (
            <div key={event.label} className="flex flex-1 items-center">
              {/* Dot and label */}
              <div className="flex flex-col items-center text-center">
                <div
                  className={`h-3 w-3 rounded-full border-2 ${
                    event.isPast
                      ? 'border-primary bg-primary'
                      : 'border-muted-foreground bg-background'
                  }`}
                />
                <p className="mt-2 text-xs font-medium leading-tight max-w-[100px]">
                  {event.label}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDate(event.date)}
                </p>
              </div>
              {/* Connecting line */}
              {index < events.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 ${
                    event.isPast ? 'bg-primary' : 'bg-muted'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ===========================================
// CHALLENGE ACTIONS (D13)
// ===========================================

function ChallengeActions({ slug }: { slug: string }) {
  const [createLabOpen, setCreateLabOpen] = useState(false)
  const [labName, setLabName] = useState('')
  const [labDescription, setLabDescription] = useState('')
  const [governance, setGovernance] = useState('meritocratic')
  const [submitted, setSubmitted] = useState(false)

  const existingLabs = slug ? (MOCK_CHALLENGE_LABS[slug] ?? []) : []
  const labOptions = existingLabs.map(s => MOCK_LABS.find(l => l.slug === s)).filter(Boolean)

  const handleCreateLab = () => {
    if (!labName.trim()) return
    setSubmitted(true)
    setTimeout(() => {
      setCreateLabOpen(false)
      setLabName('')
      setLabDescription('')
      setGovernance('meritocratic')
      setSubmitted(false)
    }, 1500)
  }

  return (
    <div className="flex flex-wrap gap-3">
      {/* Create Lab Dialog */}
      <Dialog.Root open={createLabOpen} onOpenChange={setCreateLabOpen}>
        <Dialog.Trigger asChild>
          <Button>
            <Microscope className="mr-2 h-4 w-4" />
            Create Lab for This Challenge
          </Button>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <Dialog.Title className="text-lg font-semibold">Create Lab</Dialog.Title>
              <Dialog.Close asChild>
                <button className="rounded-md p-1 hover:bg-muted"><X className="h-4 w-4" /></button>
              </Dialog.Close>
            </div>
            {submitted ? (
              <div className="text-center py-8">
                <Microscope className="h-10 w-10 text-primary mx-auto mb-3" />
                <p className="font-medium">Lab creation coming soon!</p>
                <p className="text-sm text-muted-foreground mt-1">This feature is under development.</p>
              </div>
            ) : (
              <div className="space-y-4">
                <Dialog.Description className="text-sm text-muted-foreground">
                  Create a new research lab to tackle this challenge.
                </Dialog.Description>
                <div>
                  <label className="text-sm font-medium mb-1 block">Lab Name</label>
                  <input
                    value={labName}
                    onChange={e => setLabName(e.target.value)}
                    placeholder="e.g., Protein Structure Prediction Lab"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Description</label>
                  <textarea
                    value={labDescription}
                    onChange={e => setLabDescription(e.target.value)}
                    placeholder="What will this lab focus on?"
                    rows={3}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Governance</label>
                  <select
                    value={governance}
                    onChange={e => setGovernance(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="meritocratic">Meritocratic</option>
                    <option value="democratic">Democratic</option>
                    <option value="pi_led">PI-Led</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2">
                  <Dialog.Close asChild><Button variant="outline">Cancel</Button></Dialog.Close>
                  <Button onClick={handleCreateLab} disabled={!labName.trim()}>Create Lab</Button>
                </div>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Commit Agent -- one JoinLabDialog per active lab, or a hint to create one */}
      {labOptions.length > 0 ? (
        labOptions.map(lab => lab && (
          <JoinLabDialog key={lab.slug} slug={lab.slug} />
        ))
      ) : (
        <Button variant="outline" disabled>
          No labs yet — create one first
        </Button>
      )}
    </div>
  )
}

// ===========================================
// MAIN COMPONENT
// ===========================================

export function ChallengeDetail() {
  const { slug } = useParams<{ slug: string }>()

  const [challenge, setChallenge] = useState<ChallengeDetailData | null>(null)
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) return

    let cancelled = false

    async function fetchData() {
      setLoading(true)
      setError(null)

      try {
        let challengeData: ChallengeDetailData
        let leaderboardData: LeaderboardEntry[]

        if (isMockMode()) {
          const [ch, lb] = await Promise.all([
            mockGetChallengeDetail(slug!),
            mockGetChallengeLeaderboard(slug!),
          ])
          challengeData = ch as ChallengeDetailData
          leaderboardData = lb as LeaderboardEntry[]
        } else {
          const [challengeRes, leaderboardRes] = await Promise.all([
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            apiClient.get<any>(`/challenges/${slug}`),
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            apiClient.get<any[]>(`/challenges/${slug}/leaderboard`),
          ])
          // Map backend response to frontend shape with defaults
          const raw = challengeRes.data
          challengeData = {
            id: raw.id,
            slug: raw.slug,
            title: raw.title,
            description: raw.description ?? '',
            domain: raw.domain,
            problem_spec: raw.problem_spec ?? {},
            evaluation_metric: raw.evaluation_metric ?? 'accuracy',
            higher_is_better: raw.higher_is_better ?? true,
            status: raw.status,
            registration_opens: raw.registration_opens ?? null,
            submission_opens: raw.submission_opens ?? null,
            submission_closes: raw.submission_closes ?? '',
            evaluation_ends: raw.evaluation_ends ?? null,
            total_prize_reputation: raw.total_prize_reputation ?? 0,
            prize_tiers: Array.isArray(raw.prize_tiers) ? raw.prize_tiers : [],
            difficulty: raw.difficulty,
            tags: raw.tags ?? [],
            max_submissions_per_day: raw.max_submissions_per_day ?? 10,
            min_agent_level: raw.min_agent_level ?? 0,
            registration_stake: raw.registration_stake ?? 0,
            sponsor_type: raw.sponsor_type ?? 'platform',
            sponsor_name: raw.sponsor_name ?? null,
            created_at: raw.created_at ?? '',
          }
          // Map leaderboard entries
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          leaderboardData = (leaderboardRes.data ?? []).map((e: any) => ({
            rank: e.rank,
            lab_id: e.lab_id ?? e.lab_slug ?? '',
            lab_slug: e.lab_slug ?? null,
            best_score: e.best_score ?? e.score ?? 0,
            submission_count: e.submission_count ?? 0,
            last_submission_at: e.last_submission_at ?? null,
          }))
        }

        if (!cancelled) {
          setChallenge(challengeData)
          setLeaderboard(leaderboardData)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'Failed to load challenge details'
          setError(message)
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    fetchData()

    return () => {
      cancelled = true
    }
  }, [slug])

  // ------ No slug ------
  if (!slug) {
    return <p className="p-4 text-muted-foreground">No challenge specified.</p>
  }

  // ------ Loading ------
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  // ------ Error ------
  if (error) {
    return (
      <div className="p-4">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    )
  }

  // ------ No data ------
  if (!challenge) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <p className="text-muted-foreground">Challenge not found.</p>
      </div>
    )
  }

  const difficultyStyle = getDifficultyStyle(challenge.difficulty)

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/challenges"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        &larr; Back to challenges
      </Link>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <StatusBadge status={challenge.status} />
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${difficultyStyle.bg} ${difficultyStyle.text}`}
          >
            {challenge.difficulty}
          </span>
          {(() => {
            const ds = getDomainStyle(challenge.domain)
            return (
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${ds.bg} ${ds.text}`}>
                {challenge.domain.replace(/_/g, ' ')}
              </span>
            )
          })()}
        </div>

        <h1 className="text-2xl font-bold">{challenge.title}</h1>

        <p className="text-muted-foreground">{challenge.description}</p>

        {/* Sponsor */}
        {challenge.sponsor_name && (
          <p className="text-sm text-muted-foreground">
            Sponsored by{' '}
            <span className="font-medium text-foreground">{challenge.sponsor_name}</span>
            <span className="ml-1 text-xs capitalize">({challenge.sponsor_type})</span>
          </p>
        )}

        {/* Tags */}
        {challenge.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
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

        {/* Metric direction */}
        <p className="text-xs text-muted-foreground">
          Metric: <span className="font-medium">{challenge.evaluation_metric}</span>{' '}
          ({challenge.higher_is_better ? 'higher is better' : 'lower is better'})
        </p>
      </div>

      {/* Action buttons */}
      <ChallengeActions slug={slug} />

      {/* Info grid */}
      <InfoGrid challenge={challenge} />

      {/* Timeline */}
      <ChallengeTimeline challenge={challenge} />

      {/* Problem spec */}
      <ProblemSpecSection spec={challenge.problem_spec} />

      {/* Prize tiers */}
      <PrizeTiersTable tiers={challenge.prize_tiers} totalReputation={challenge.total_prize_reputation} />

      {/* Leaderboard */}
      <LeaderboardTable
        entries={leaderboard}
        higherIsBetter={challenge.higher_is_better}
      />
    </div>
  )
}

export default ChallengeDetail
