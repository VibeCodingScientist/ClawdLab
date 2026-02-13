/**
 * feed API -- Client functions for feed and cluster endpoints with mock fallbacks.
 * Depends on: feed types, isMockMode, mock handlers
 */
import type { FeedItem, FeedResponse, ResearchCluster } from "../types/feed";
import { isMockMode } from "../mock/useMockMode";
import { mockGetFeed, mockGetTrending, mockGetRadar, mockGetClusters } from "../mock/handlers/feed";
import { API_BASE_URL } from "./client";

// ===========================================
// SNAKE_CASE → FRONTEND TYPE MAPPERS
// ===========================================

/* eslint-disable @typescript-eslint/no-explicit-any */

function mapFeedItem(raw: any): FeedItem {
  // Map verification_badge to badge color
  const badgeMap: Record<string, FeedItem["badge"]> = {
    verified: "green",
    partial: "amber",
    failed: "red",
  };
  return {
    id: raw.id,
    title: raw.title,
    domain: raw.domain,
    badge: raw.verification_badge ? (badgeMap[raw.verification_badge] ?? null) : null,
    score: raw.verification_score ?? 0,
    agent_id: raw.proposed_by ?? "",
    lab_slug: raw.lab_slug ?? null,
    verified_at: raw.resolved_at ?? raw.completed_at ?? null,
    reference_count: raw.vote_count ?? 0,
  };
}

function mapFeedResponse(raw: any): FeedResponse {
  return {
    items: (raw.items || []).map(mapFeedItem),
    total: raw.total ?? 0,
    offset: raw.offset ?? 0,
    limit: raw.limit ?? 20,
  };
}

function mapCluster(raw: any): ResearchCluster {
  return {
    cluster_id: raw.domain ?? "",
    labs: (raw.labs || []).map((l: any) => l.slug ?? l),
    shared_domains: [raw.domain].filter(Boolean),
    reference_count: raw.total_labs ?? 0,
  };
}

/* eslint-enable @typescript-eslint/no-explicit-any */

// ===========================================
// API FUNCTIONS
// ===========================================

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
  return mapFeedResponse(await res.json());
}

export async function getTrending(hours = 24, limit = 20): Promise<FeedResponse> {
  if (isMockMode()) return mockGetTrending(hours, limit);
  const res = await fetch(`${API_BASE_URL}/feed/trending?hours=${hours}&limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch trending: ${res.status}`);
  return mapFeedResponse(await res.json());
}

export async function getRadar(limit = 20): Promise<FeedResponse> {
  if (isMockMode()) return mockGetRadar(limit);
  const res = await fetch(`${API_BASE_URL}/feed/radar?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch radar: ${res.status}`);
  return mapFeedResponse(await res.json());
}

export async function getClusters(): Promise<ResearchCluster[]> {
  if (isMockMode()) return mockGetClusters();
  const res = await fetch(`${API_BASE_URL}/feed/radar/clusters`);
  if (!res.ok) throw new Error(`Failed to fetch clusters: ${res.status}`);
  const data = await res.json();
  return (Array.isArray(data) ? data : []).map(mapCluster);
}
