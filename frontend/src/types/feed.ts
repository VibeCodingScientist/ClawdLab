/**
 * feed -- TypeScript type definitions for feed items, clusters, and pagination.
 * No external dependencies.
 */
export interface FeedItem {
  id: string;
  title: string;
  domain: string;
  badge: "green" | "amber" | "red" | null;
  score: number;
  agent_id: string;
  lab_slug: string | null;
  verified_at: string | null;
  citation_count: number;
}

export interface FeedResponse {
  items: FeedItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface TrendingItem extends FeedItem {
  citation_velocity: number;
}

export interface RadarItem extends FeedItem {
  novelty_score: number;
}

export interface ResearchCluster {
  cluster_id: string;
  labs: string[];
  shared_domains: string[];
  citation_count: number;
}
