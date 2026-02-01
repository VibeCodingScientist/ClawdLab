/**
 * feed API -- Client functions for feed and cluster endpoints with mock fallbacks.
 * Depends on: feed types, isMockMode, mock handlers
 */
import type { FeedResponse, ResearchCluster } from "../types/feed";
import { isMockMode } from "../mock/useMockMode";
import { mockGetFeed, mockGetTrending, mockGetRadar, mockGetClusters } from "../mock/handlers/feed";
import { API_BASE_URL } from "./client";

export async function getFeed(params?: {
  domain?: string;
  offset?: number;
  limit?: number;
}): Promise<FeedResponse> {
  if (isMockMode()) return mockGetFeed(params);
  const searchParams = new URLSearchParams();
  if (params?.domain) searchParams.set("domain", params.domain);
  if (params?.offset != null) searchParams.set("offset", String(params.offset));
  if (params?.limit != null) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  const res = await fetch(`${API_BASE_URL}/feed${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`Failed to fetch feed: ${res.status}`);
  return res.json();
}

export async function getTrending(hours = 24, limit = 20): Promise<FeedResponse> {
  if (isMockMode()) return mockGetTrending(hours, limit);
  const res = await fetch(`${API_BASE_URL}/feed/trending?hours=${hours}&limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch trending: ${res.status}`);
  return res.json();
}

export async function getRadar(limit = 20): Promise<FeedResponse> {
  if (isMockMode()) return mockGetRadar(limit);
  const res = await fetch(`${API_BASE_URL}/feed/radar?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch radar: ${res.status}`);
  return res.json();
}

export async function getClusters(): Promise<ResearchCluster[]> {
  if (isMockMode()) return mockGetClusters();
  const res = await fetch(`${API_BASE_URL}/feed/radar/clusters`);
  if (!res.ok) throw new Error(`Failed to fetch clusters: ${res.status}`);
  return res.json();
}
