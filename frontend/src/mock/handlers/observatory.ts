import { MOCK_DELAY_MS } from '../useMockMode'
import { MOCK_LAB_IMPACT } from '../mockData'
import type { CitationMetrics, LabImpact } from '@/api/observatory'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

export function mockGetCitationMetrics(claimId: string): Promise<CitationMetrics> {
  return delay({
    claim_id: claimId,
    direct_citations: Math.floor(Math.random() * 20) + 1,
    indirect_citations: Math.floor(Math.random() * 10),
    cross_lab_citations: Math.floor(Math.random() * 5),
    total_impact: Math.random() * 50 + 10,
  })
}

export function mockGetLabImpact(slug: string): Promise<LabImpact> {
  const impact = MOCK_LAB_IMPACT[slug]
  if (!impact) {
    return Promise.reject(new Error(`Lab ${slug} not found`))
  }
  return delay(impact)
}
