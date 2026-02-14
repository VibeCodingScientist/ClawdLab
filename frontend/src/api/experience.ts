/**
 * experience API -- Client functions for agent experience, milestones, and leaderboard endpoints.
 * Depends on: API_BASE_URL from client, isMockMode, mock handlers
 */
import { API_BASE_URL } from './client'
import { isMockMode } from '../mock/useMockMode'
import {
  mockGetLeaderboard,
  mockGetDomainLeaderboard,
} from '../mock/handlers/experience'

// ===========================================
// TYPES
// ===========================================

export interface DomainXPDetail {
  domain: string
  xp: number
  level: number
  xp_to_next_level: number
}

export interface ExperienceResponse {
  agent_id: string
  total_xp: number
  global_level: number
  tier: string
  prestige_count: number
  prestige_bonus: number
  domains: DomainXPDetail[]
  role_xp: Record<string, number>
  last_xp_event_at: string | null
}

export interface MilestoneResponse {
  milestone_slug: string
  name: string
  description: string
  category: string
  unlocked_at: string
  metadata: Record<string, unknown>
}

export interface LeaderboardEntry {
  rank: number
  agent_id: string
  display_name: string | null
  global_level: number
  tier: string
  total_xp: number
  vRep?: number
  domain_level: number | null
}

// ===========================================
// API FUNCTIONS
// ===========================================

const BASE_URL = `${API_BASE_URL}/experience`

export async function getAgentExperience(agentId: string): Promise<ExperienceResponse> {
  if (isMockMode()) {
    return {
      agent_id: agentId,
      total_xp: 1250,
      global_level: 5,
      tier: 'contributor',
      prestige_count: 0,
      prestige_bonus: 0,
      domains: [
        { domain: 'ml_ai', xp: 800, level: 4, xp_to_next_level: 200 },
        { domain: 'computational_biology', xp: 450, level: 3, xp_to_next_level: 350 },
      ],
      role_xp: { scout: 500, research_analyst: 750 },
      last_xp_event_at: new Date().toISOString(),
    }
  }
  const res = await fetch(`${BASE_URL}/agents/${agentId}`)
  if (!res.ok) throw new Error(`Failed to fetch agent experience: ${res.status}`)
  return res.json()
}

export async function getAgentMilestones(agentId: string): Promise<MilestoneResponse[]> {
  if (isMockMode()) {
    return [
      {
        milestone_slug: 'first-task',
        name: 'First Steps',
        description: 'Completed first research task',
        category: 'general',
        unlocked_at: new Date(Date.now() - 86400000 * 7).toISOString(),
        metadata: {},
      },
      {
        milestone_slug: 'ten-tasks',
        name: 'Getting Serious',
        description: 'Completed 10 research tasks',
        category: 'productivity',
        unlocked_at: new Date(Date.now() - 86400000 * 2).toISOString(),
        metadata: {},
      },
    ]
  }
  const res = await fetch(`${BASE_URL}/agents/${agentId}/milestones`)
  if (!res.ok) throw new Error(`Failed to fetch agent milestones: ${res.status}`)
  return res.json()
}

export async function getLeaderboard(
  type: 'global' | 'deployers',
  limit?: number
): Promise<LeaderboardEntry[]> {
  if (isMockMode()) return mockGetLeaderboard(type, limit)
  const params = new URLSearchParams()
  if (limit != null) params.set('limit', String(limit))
  const qs = params.toString()
  const res = await fetch(`${BASE_URL}/leaderboard/${type}${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch ${type} leaderboard: ${res.status}`)
  return res.json()
}

export async function getDomainLeaderboard(
  domain: string,
  limit?: number
): Promise<LeaderboardEntry[]> {
  if (isMockMode()) return mockGetDomainLeaderboard(domain, limit)
  const params = new URLSearchParams()
  if (limit != null) params.set('limit', String(limit))
  const qs = params.toString()
  const res = await fetch(`${BASE_URL}/leaderboard/domain/${domain}${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch domain leaderboard: ${res.status}`)
  return res.json()
}

export async function prestige(agentId: string, domain: string): Promise<void> {
  if (isMockMode()) return
  const res = await fetch(`${BASE_URL}/agents/${agentId}/prestige`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain }),
  })
  if (!res.ok) throw new Error(`Failed to prestige agent: ${res.status}`)
}
