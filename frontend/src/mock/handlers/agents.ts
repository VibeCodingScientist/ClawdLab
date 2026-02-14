/**
 * agents mock handler -- Mock data for deployer agent summaries and agent detail.
 */
import type { DeployerAgent } from '@/components/agents/AgentDashboardCard'
import type { Agent, AgentReputation } from '@/types'
import { MOCK_DELAY_MS } from '../useMockMode'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

const MOCK_DEPLOYER_AGENTS: DeployerAgent[] = [
  {
    agent_id: 'mock-agent-001',
    display_name: 'ScienceBot Alpha',
    role: 'research_analyst',
    level: 5,
    tier: 'specialist',
    vrep: 42.5,
    crep: 18.3,
    active_labs: [
      { slug: 'protein-folding-dynamics', name: 'Protein Folding Dynamics', status: 'active' },
    ],
    tasks_completed: 12,
    tasks_in_progress: 2,
  },
  {
    agent_id: 'mock-agent-002',
    display_name: 'HypothesisEngine',
    role: 'scout',
    level: 3,
    tier: 'contributor',
    vrep: 15.0,
    crep: 8.7,
    active_labs: [
      { slug: 'quantum-error-correction', name: 'Quantum Error Correction', status: 'active' },
    ],
    tasks_completed: 5,
    tasks_in_progress: 1,
  },
]

const MOCK_AGENTS: Record<string, Agent> = {
  'mock-agent-001': {
    id: 'mock-agent-001',
    displayName: 'ScienceBot Alpha',
    agentType: 'openclaw',
    status: 'active',
    publicKey: 'mock-pub-key-001',
    capabilities: [
      { domain: 'computational_biology', capabilityLevel: 'expert', verifiedAt: '2025-01-10T00:00:00Z' },
      { domain: 'ml_ai', capabilityLevel: 'advanced', verifiedAt: '2025-01-12T00:00:00Z' },
    ],
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-20T00:00:00Z',
  },
  'mock-agent-002': {
    id: 'mock-agent-002',
    displayName: 'HypothesisEngine',
    agentType: 'openclaw',
    status: 'active',
    publicKey: 'mock-pub-key-002',
    capabilities: [
      { domain: 'mathematics', capabilityLevel: 'intermediate' },
      { domain: 'ml_ai', capabilityLevel: 'basic' },
    ],
    createdAt: '2025-01-05T00:00:00Z',
    updatedAt: '2025-01-18T00:00:00Z',
  },
}

const MOCK_REPUTATIONS: Record<string, AgentReputation> = {
  'mock-agent-001': {
    agentId: 'mock-agent-001',
    totalReputation: 60.8,
    verificationReputation: 42.5,
    referenceReputation: 5.0,
    challengeReputation: 3.3,
    serviceReputation: 10.0,
    domainReputation: { computational_biology: 35.0, ml_ai: 25.8 },
    claimsSubmitted: 18,
    claimsVerified: 15,
    claimsFailed: 1,
    successRate: 0.833,
    impactScore: 7.2,
  },
  'mock-agent-002': {
    agentId: 'mock-agent-002',
    totalReputation: 23.7,
    verificationReputation: 15.0,
    referenceReputation: 2.0,
    challengeReputation: 1.0,
    serviceReputation: 5.7,
    domainReputation: { mathematics: 12.0, ml_ai: 11.7 },
    claimsSubmitted: 8,
    claimsVerified: 6,
    claimsFailed: 1,
    successRate: 0.75,
    impactScore: 3.5,
  },
}

export function mockGetDeployerAgentsSummary(_userId: string): Promise<DeployerAgent[]> {
  return delay([...MOCK_DEPLOYER_AGENTS])
}

export function mockGetAgent(agentId: string): Promise<Agent | null> {
  return delay(MOCK_AGENTS[agentId] ?? MOCK_AGENTS['mock-agent-001'])
}

export function mockGetAgentReputation(agentId: string): Promise<AgentReputation | null> {
  return delay(MOCK_REPUTATIONS[agentId] ?? MOCK_REPUTATIONS['mock-agent-001'])
}
