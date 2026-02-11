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
  const res = await fetch(`${BASE_URL}/agents/${agentId}`)
  if (!res.ok) throw new Error(`Failed to fetch agent experience: ${res.status}`)
  return res.json()
}

export async function getAgentMilestones(agentId: string): Promise<MilestoneResponse[]> {
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
  const res = await fetch(`${BASE_URL}/agents/${agentId}/prestige`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ domain }),
  })
  if (!res.ok) throw new Error(`Failed to prestige agent: ${res.status}`)
}
