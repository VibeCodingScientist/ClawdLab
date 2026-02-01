import { MOCK_DELAY_MS } from '../useMockMode'
import { MOCK_FEED_ITEMS, MOCK_CLUSTERS } from '../mockData'
import type { FeedResponse, ResearchCluster } from '@/types/feed'

function delay<T>(data: T): Promise<T> {
  return new Promise(resolve => setTimeout(() => resolve(data), MOCK_DELAY_MS))
}

export function mockGetFeed(params?: {
  domain?: string
  offset?: number
  limit?: number
}): Promise<FeedResponse> {
  let items = [...MOCK_FEED_ITEMS]
  if (params?.domain) {
    items = items.filter(i => i.domain === params.domain)
  }
  const offset = params?.offset ?? 0
  const limit = params?.limit ?? 50
  const sliced = items.slice(offset, offset + limit)
  return delay({
    items: sliced,
    total: items.length,
    offset,
    limit,
  })
}

export function mockGetTrending(_hours = 24, limit = 20): Promise<FeedResponse> {
  const sorted = [...MOCK_FEED_ITEMS].sort((a, b) => b.citation_count - a.citation_count).slice(0, limit)
  return delay({
    items: sorted,
    total: sorted.length,
    offset: 0,
    limit,
  })
}

export function mockGetRadar(limit = 20): Promise<FeedResponse> {
  const sorted = [...MOCK_FEED_ITEMS].sort((a, b) => b.score - a.score).slice(0, limit)
  return delay({
    items: sorted,
    total: sorted.length,
    offset: 0,
    limit,
  })
}

export function mockGetClusters(): Promise<ResearchCluster[]> {
  return delay(MOCK_CLUSTERS)
}
