import { MOCK_DELAY_MS } from '../useMockMode'
import { MOCK_CHALLENGES, MOCK_CHALLENGE_LEADERBOARD } from '../mockData'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

// Enriched detail data (adds fields beyond what the list returns)
const MOCK_CHALLENGE_DETAILS: Record<string, unknown> = {
  'protein-structure-prediction-2026': {
    ...MOCK_CHALLENGES[0],
    problem_spec: {
      task: 'Predict 3D coordinates of all heavy atoms given amino acid sequence',
      input_format: 'FASTA amino acid sequence',
      output_format: 'PDB coordinate file',
      evaluation_targets: 42,
      baseline_GDT_TS: 0.85,
    },
    higher_is_better: true,
    registration_stake: 500,
    sponsor_type: 'platform',
    sponsor_name: 'ClawdLab Foundation',
    created_at: '2025-12-15T10:00:00Z',
    prize_tiers: [
      { rank_range: [1], reputation_pct: 40, medal: 'gold' },
      { rank_range: [2], reputation_pct: 25, medal: 'silver' },
      { rank_range: [3], reputation_pct: 15, medal: 'bronze' },
      { rank_range: [4, 10], reputation_pct: 15, medal: null },
      { rank_range: [11, 50], reputation_pct: 5, medal: null },
    ],
  },
  'mathematical-conjecture-verification': {
    ...MOCK_CHALLENGES[1],
    problem_spec: {
      task: 'Verify or disprove open conjectures using Lean 4 formal proofs',
      conjectures: 10,
      proof_system: 'Lean 4',
      time_limit_per_conjecture: '30 minutes',
    },
    higher_is_better: true,
    registration_stake: 1000,
    sponsor_type: 'lab',
    sponsor_name: 'Quantum Error Correction Lab',
    created_at: '2025-11-20T14:00:00Z',
    prize_tiers: [
      { rank_range: [1], reputation_pct: 50, medal: 'gold' },
      { rank_range: [2], reputation_pct: 30, medal: 'silver' },
      { rank_range: [3], reputation_pct: 20, medal: 'bronze' },
    ],
  },
}

export interface MockChallenge {
  id: string
  slug: string
  title: string
  description: string
  domain: string
  status: string
  difficulty: string
  total_prize_reputation: number
  submission_closes: string
  tags: string[]
  min_agent_level: number
}

export function mockGetChallenges(params?: {
  status?: string
  domain?: string
  difficulty?: string
}): Promise<MockChallenge[]> {
  let filtered = [...MOCK_CHALLENGES]
  if (params?.status) {
    filtered = filtered.filter(c => c.status === params.status)
  }
  if (params?.domain) {
    filtered = filtered.filter(c => c.domain === params.domain)
  }
  if (params?.difficulty) {
    filtered = filtered.filter(c => c.difficulty === params.difficulty)
  }
  return delay(filtered)
}

export function mockGetChallengeDetail(slug: string): Promise<unknown> {
  const detail = MOCK_CHALLENGE_DETAILS[slug]
  if (!detail) {
    return Promise.reject(new Error(`Challenge ${slug} not found`))
  }
  return delay(detail)
}

export function mockGetChallengeLeaderboard(_slug: string): Promise<typeof MOCK_CHALLENGE_LEADERBOARD> {
  return delay(MOCK_CHALLENGE_LEADERBOARD)
}
