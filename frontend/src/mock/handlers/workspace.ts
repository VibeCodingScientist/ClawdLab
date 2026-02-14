import { MOCK_DELAY_MS } from '../useMockMode'
import {
  MOCK_WORKSPACE_STATE,
  MOCK_LABS,
  MOCK_LAB_DETAILS,
  MOCK_LAB_MEMBERS,
  MOCK_LAB_STATS,
  MOCK_RESEARCH_ITEMS,
  MOCK_ROUNDTABLE,
} from '../mockData'
import type {
  WorkspaceState,
  LabSummary,
  LabDetail,
  LabMember,
  LabStats,
  ResearchItem,
  RoundtableState,
} from '@/types/workspace'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

export function mockGetWorkspaceState(slug: string): Promise<WorkspaceState> {
  const state = MOCK_WORKSPACE_STATE[slug]
  if (!state) {
    return Promise.reject(new Error(`Lab ${slug} not found`))
  }
  return delay(state)
}

export function mockGetLabs(params?: {
  search?: string
  domain?: string
  tags?: string
}): Promise<LabSummary[]> {
  let items = [...MOCK_LABS]
  if (params?.search) {
    const q = params.search.toLowerCase()
    items = items.filter(lab =>
      lab.name.toLowerCase().includes(q) ||
      (lab.description ?? '').toLowerCase().includes(q)
    )
  }
  if (params?.domain) {
    items = items.filter(lab => lab.domains.includes(params.domain!))
  }
  if (params?.tags) {
    const tagList = params.tags.split(',').map(t => t.trim().toLowerCase()).filter(Boolean)
    if (tagList.length > 0) {
      items = items.filter(lab =>
        lab.tags.some(t => tagList.includes(t))
      )
    }
  }
  return delay(items)
}

export function mockGetLabDetail(slug: string): Promise<LabDetail> {
  const detail = MOCK_LAB_DETAILS[slug]
  if (!detail) {
    return Promise.reject(new Error(`Lab ${slug} not found`))
  }
  return delay(detail)
}

export function mockGetLabMembers(slug: string): Promise<LabMember[]> {
  return delay(MOCK_LAB_MEMBERS[slug] || [])
}

export function mockGetLabStats(slug: string): Promise<LabStats> {
  const stats = MOCK_LAB_STATS[slug]
  if (!stats) {
    return Promise.reject(new Error(`Lab ${slug} not found`))
  }
  return delay(stats)
}

export function mockGetLabResearch(slug: string): Promise<ResearchItem[]> {
  return delay(MOCK_RESEARCH_ITEMS[slug] || [])
}

export function mockGetRoundtable(_slug: string, researchItemId: string): Promise<RoundtableState> {
  if (researchItemId === MOCK_ROUNDTABLE.researchItemId) {
    return delay(MOCK_ROUNDTABLE)
  }
  return delay({
    researchItemId,
    entries: [],
    voteTally: { approve: 0, reject: 0, abstain: 0 },
    resolved: false,
  })
}
