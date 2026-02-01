/**
 * observatory API -- Client functions for observatory and impact data endpoints.
 * Depends on: isMockMode, mock handlers
 */
import { isMockMode } from "../mock/useMockMode";
import { mockGetCitationMetrics, mockGetLabImpact } from "../mock/handlers/observatory";
import { API_BASE_URL } from "./client";

export interface CitationMetrics {
  claim_id: string;
  direct_citations: number;
  indirect_citations: number;
  cross_lab_citations: number;
  total_impact: number;
}

export interface LabImpact {
  slug: string;
  total_claims: number;
  verified_claims: number;
  citations_received: number;
  citations_given: number;
  cross_lab_ratio: number;
  h_index: number;
}

export async function getCitationMetrics(claimId: string): Promise<CitationMetrics> {
  if (isMockMode()) return mockGetCitationMetrics(claimId);
  const res = await fetch(`${API_BASE_URL}/feed/claims/${claimId}/citations`);
  if (!res.ok) throw new Error(`Failed to fetch citation metrics: ${res.status}`);
  return res.json();
}

export async function getLabImpact(slug: string): Promise<LabImpact> {
  if (isMockMode()) return mockGetLabImpact(slug);
  const res = await fetch(`${API_BASE_URL}/feed/labs/${slug}/impact`);
  if (!res.ok) throw new Error(`Failed to fetch lab impact: ${res.status}`);
  return res.json();
}
