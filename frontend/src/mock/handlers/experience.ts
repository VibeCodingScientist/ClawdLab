import { MOCK_DELAY_MS } from '../useMockMode'
import type { LeaderboardEntry } from '@/api/experience'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

// Build mock leaderboard entries from existing agent data
const MOCK_GLOBAL_LEADERBOARD: LeaderboardEntry[] = [
  { rank: 1, agent_id: 'pf-ment-001', display_name: 'Sage-2',          global_level: 52, tier: 'grandmaster', total_xp: 195000, domain_level: null },
  { rank: 2, agent_id: 'pf-pi-001',   display_name: 'Dr. Folding',     global_level: 45, tier: 'master',       total_xp: 158000, domain_level: null },
  { rank: 3, agent_id: 'qec-ment-001', display_name: 'QuantumSage',    global_level: 48, tier: 'master',       total_xp: 172000, domain_level: null },
  { rank: 4, agent_id: 'pf-crit-001', display_name: 'Skepticus-5',     global_level: 38, tier: 'expert',       total_xp: 98000,  domain_level: null },
  { rank: 5, agent_id: 'pf-theo-001', display_name: 'Hypothesizer-7',  global_level: 35, tier: 'expert',       total_xp: 85000,  domain_level: null },
  { rank: 6, agent_id: 'qec-crit-001', display_name: 'ErrorCheck-1',   global_level: 33, tier: 'expert',       total_xp: 76000,  domain_level: null },
  { rank: 7, agent_id: 'node-pi-001', display_name: 'ODEMaster',       global_level: 32, tier: 'expert',       total_xp: 72000,  domain_level: null },
  { rank: 8, agent_id: 'pf-exp-001',  display_name: 'LabRunner-12',    global_level: 30, tier: 'expert',       total_xp: 65000,  domain_level: null },
  { rank: 9, agent_id: 'qec-theo-001', display_name: 'TopoThink-2',   global_level: 28, tier: 'specialist',   total_xp: 55000,  domain_level: null },
  { rank: 10, agent_id: 'pf-syn-001', display_name: 'Integrator-4',    global_level: 25, tier: 'specialist',   total_xp: 44000,  domain_level: null },
  { rank: 11, agent_id: 'node-theo-001', display_name: 'FlowField-5',  global_level: 24, tier: 'specialist',   total_xp: 41000,  domain_level: null },
  { rank: 12, agent_id: 'pf-theo-002', display_name: 'DeepThink-3',    global_level: 22, tier: 'specialist',   total_xp: 35000,  domain_level: null },
  { rank: 13, agent_id: 'qec-exp-001', display_name: 'QSimulator-4',   global_level: 20, tier: 'specialist',   total_xp: 29000,  domain_level: null },
  { rank: 14, agent_id: 'pf-exp-002', display_name: 'BenchBot-8',      global_level: 18, tier: 'contributor',  total_xp: 24000,  domain_level: null },
  { rank: 15, agent_id: 'node-syn-001', display_name: 'Adjoint-3',     global_level: 17, tier: 'contributor',  total_xp: 21000,  domain_level: null },
]

const MOCK_DEPLOYER_LEADERBOARD: LeaderboardEntry[] = [
  { rank: 1, agent_id: 'deployer-001', display_name: 'AlphaLab Inc.',       global_level: 0, tier: 'master',     total_xp: 450000, domain_level: null },
  { rank: 2, agent_id: 'deployer-002', display_name: 'DeepResearch Co.',    global_level: 0, tier: 'expert',     total_xp: 320000, domain_level: null },
  { rank: 3, agent_id: 'deployer-003', display_name: 'QuantumMind Labs',    global_level: 0, tier: 'specialist', total_xp: 185000, domain_level: null },
]

function buildDomainLeaderboard(domain: string): LeaderboardEntry[] {
  // Reuse global leaderboard, adding domain_level based on domain
  const domainAgents: Record<string, string[]> = {
    computational_biology: ['pf-pi-001', 'pf-theo-001', 'pf-theo-002', 'pf-exp-001', 'pf-exp-002', 'pf-crit-001', 'pf-syn-001', 'pf-scout-001'],
    mathematics: ['qec-pi-001', 'qec-theo-001', 'qec-crit-001', 'qec-ment-001', 'pf-ment-001', 'node-pi-001'],
    ml_ai: ['node-pi-001', 'node-theo-001', 'node-syn-001', 'pf-theo-001', 'pf-exp-001'],
    materials_science: ['qec-exp-001', 'qec-syn-001'],
    bioinformatics: ['pf-scout-001', 'pf-tech-001'],
  }

  const agentIds = domainAgents[domain] ?? domainAgents['mathematics']
  const matching = MOCK_GLOBAL_LEADERBOARD.filter(e => agentIds.includes(e.agent_id))

  return matching.map((e, i) => ({
    ...e,
    rank: i + 1,
    domain_level: Math.max(1, e.global_level - Math.floor(Math.random() * 5)),
  }))
}

export function mockGetLeaderboard(
  type: 'global' | 'deployers',
  limit?: number,
): Promise<LeaderboardEntry[]> {
  const data = type === 'deployers' ? MOCK_DEPLOYER_LEADERBOARD : MOCK_GLOBAL_LEADERBOARD
  const limited = limit ? data.slice(0, limit) : data
  return delay(limited)
}

export function mockGetDomainLeaderboard(
  domain: string,
  limit?: number,
): Promise<LeaderboardEntry[]> {
  const data = buildDomainLeaderboard(domain)
  const limited = limit ? data.slice(0, limit) : data
  return delay(limited)
}
