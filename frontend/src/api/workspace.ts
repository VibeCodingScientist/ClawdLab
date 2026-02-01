/**
 * workspace API -- Client functions for workspace endpoints with mock fallbacks in demo mode.
 * Depends on: workspace types, isMockMode, mock handlers
 */
import type {
  WorkspaceState,
  LabSummary,
  LabDetail,
  LabMember,
  LabStats,
  ResearchItem,
  RoundtableState,
} from "../types/workspace";
import { isMockMode } from "../mock/useMockMode";
import {
  mockGetWorkspaceState,
  mockGetLabs,
  mockGetLabDetail,
  mockGetLabMembers,
  mockGetLabStats,
  mockGetLabResearch,
  mockGetRoundtable,
} from "../mock/handlers/workspace";
import { API_BASE_URL } from "./client";

export async function getWorkspaceState(slug: string): Promise<WorkspaceState> {
  if (isMockMode()) return mockGetWorkspaceState(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/workspace/state`);
  if (!res.ok) throw new Error(`Failed to fetch workspace state: ${res.status}`);
  return res.json();
}

export function createWorkspaceSSE(slug: string): EventSource {
  return new EventSource(`${API_BASE_URL}/labs/${slug}/workspace/stream`);
}

export async function getLabs(): Promise<LabSummary[]> {
  if (isMockMode()) return mockGetLabs();
  const res = await fetch(`${API_BASE_URL}/labs`);
  if (!res.ok) throw new Error(`Failed to fetch labs: ${res.status}`);
  return res.json();
}

export async function getLabDetail(slug: string): Promise<LabDetail> {
  if (isMockMode()) return mockGetLabDetail(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}`);
  if (!res.ok) throw new Error(`Failed to fetch lab detail: ${res.status}`);
  return res.json();
}

export async function getLabMembers(slug: string): Promise<LabMember[]> {
  if (isMockMode()) return mockGetLabMembers(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/members`);
  if (!res.ok) throw new Error(`Failed to fetch lab members: ${res.status}`);
  return res.json();
}

export async function getLabStats(slug: string): Promise<LabStats> {
  if (isMockMode()) return mockGetLabStats(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/stats`);
  if (!res.ok) throw new Error(`Failed to fetch lab stats: ${res.status}`);
  return res.json();
}

export async function getLabResearch(slug: string): Promise<ResearchItem[]> {
  if (isMockMode()) return mockGetLabResearch(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/research`);
  if (!res.ok) throw new Error(`Failed to fetch lab research: ${res.status}`);
  return res.json();
}

export async function getRoundtable(slug: string, researchItemId: string): Promise<RoundtableState> {
  if (isMockMode()) return mockGetRoundtable(slug, researchItemId);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/roundtable/${researchItemId}`);
  if (!res.ok) throw new Error(`Failed to fetch roundtable: ${res.status}`);
  return res.json();
}
