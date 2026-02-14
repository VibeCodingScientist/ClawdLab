/**
 * agents mock handler -- Mock data for deployer agent summaries.
 */
import type { DeployerAgent } from '@/components/agents/AgentDashboardCard'
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

export function mockGetDeployerAgentsSummary(_userId: string): Promise<DeployerAgent[]> {
  return delay([...MOCK_DEPLOYER_AGENTS])
}
