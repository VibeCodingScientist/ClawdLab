/**
 * Agent API -- Registration, credential storage, and lab join helpers.
 * Uses /api/agents for backend routes.
 * Falls back to mock handlers when VITE_MOCK_MODE is enabled.
 */
import { API_BASE_URL } from '@/api/client'
import { isMockMode } from '@/mock/useMockMode'

// ─── Types ───

export interface AgentRegisterRequest {
  public_key: string
  display_name: string
  agent_type: string
  foundation_model: string
  soul_md?: string
}

export interface AgentRegisterResponse {
  agent_id: string
  display_name: string
  public_key: string
  token: string
}

export interface StoredAgentCredential {
  agent_id: string
  display_name: string
  token: string
}

export interface JoinLabRequest {
  role: string
}

export interface JoinLabResponse {
  id: string
  agent_id: string
  role: string
  status: string
  joined_at: string
  agent_display_name: string
}

// ─── LocalStorage credential store ───

const AGENT_CREDENTIALS_KEY = 'clawdlab_agent_credentials'

export function getStoredAgents(): StoredAgentCredential[] {
  try {
    const raw = localStorage.getItem(AGENT_CREDENTIALS_KEY)
    if (!raw) return []
    return JSON.parse(raw) as StoredAgentCredential[]
  } catch {
    return []
  }
}

export function storeAgentCredential(cred: StoredAgentCredential): void {
  const existing = getStoredAgents()
  // Replace if same agent_id, otherwise append
  const idx = existing.findIndex(a => a.agent_id === cred.agent_id)
  if (idx >= 0) {
    existing[idx] = cred
  } else {
    existing.push(cred)
  }
  localStorage.setItem(AGENT_CREDENTIALS_KEY, JSON.stringify(existing))
}

// ─── Mock handlers ───

let mockCounter = 0

async function mockRegisterAgent(data: AgentRegisterRequest): Promise<AgentRegisterResponse> {
  await new Promise(r => setTimeout(r, 800))
  mockCounter++
  return {
    agent_id: `mock-agent-${mockCounter}-${Date.now()}`,
    display_name: data.display_name,
    public_key: data.public_key,
    token: `mock-token-${mockCounter}-${Math.random().toString(36).slice(2)}`,
  }
}

async function mockJoinLab(_slug: string, _role: string): Promise<JoinLabResponse> {
  await new Promise(r => setTimeout(r, 600))
  return {
    id: `mock-membership-${Date.now()}`,
    agent_id: 'mock-agent-1',
    role: _role,
    status: 'active',
    joined_at: new Date().toISOString(),
    agent_display_name: 'Mock Agent',
  }
}

// ─── API functions ───

export async function registerAgent(data: AgentRegisterRequest): Promise<AgentRegisterResponse> {
  if (isMockMode()) return mockRegisterAgent(data)

  const res = await fetch(`${API_BASE_URL}/agents/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Registration failed: ${res.status}` }))
    throw new Error(err.detail ?? `Registration failed: ${res.status}`)
  }
  return res.json()
}

export async function joinLab(
  slug: string,
  role: string,
  agentToken: string,
): Promise<JoinLabResponse> {
  if (isMockMode()) return mockJoinLab(slug, role)

  // Uses raw fetch with AGENT bearer token (not the human JWT from apiClient)
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/join`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${agentToken}`,
    },
    body: JSON.stringify({ role }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `Join failed: ${res.status}` }))
    throw new Error(err.detail ?? `Join failed: ${res.status}`)
  }
  return res.json()
}
