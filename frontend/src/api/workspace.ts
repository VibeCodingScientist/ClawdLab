/**
 * workspace API -- Client functions for workspace endpoints with mock fallbacks in demo mode.
 * Depends on: workspace types, isMockMode, mock handlers
 */
import type {
  WorkspaceState,
  WorkspaceAgent,
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

// ===========================================
// SNAKE_CASE → CAMELCASE MAPPERS
// ===========================================

/* eslint-disable @typescript-eslint/no-explicit-any */

function mapWorkspaceAgent(raw: any): WorkspaceAgent {
  return {
    agent_id: raw.agent_id,
    zone: raw.zone,
    position_x: raw.position?.x ?? 0,
    position_y: raw.position?.y ?? 0,
    status: raw.status,
    last_action_at: null,
  };
}

function mapWorkspaceState(raw: any): WorkspaceState {
  return {
    slug: raw.lab_slug,
    agents: (raw.agents || []).map(mapWorkspaceAgent),
    total: raw.active_tasks ?? (raw.agents || []).length,
  };
}

function mapLabSummary(raw: any): LabSummary {
  return {
    slug: raw.slug,
    name: raw.name,
    description: raw.description,
    domains: raw.domains ?? [],
    memberCount: raw.member_count ?? 0,
    governanceType: raw.governance_type,
    visibility: "public",
  };
}

function mapLabDetail(raw: any): LabDetail {
  return {
    ...mapLabSummary(raw),
    openRoles: [],
    createdAt: raw.created_at,
  };
}

function mapLabMember(raw: any): LabMember {
  return {
    agentId: raw.agent_id,
    displayName: raw.display_name,
    archetype: raw.role,
    vRep: raw.vrep ?? 0,
    cRep: raw.crep ?? 0,
    reputation: (raw.vrep ?? 0) + (raw.crep ?? 0),
    claimsCount: 0,
    joinedAt: raw.joined_at,
  };
}

function mapLabStats(raw: any): LabStats {
  return {
    totalClaims: raw.total_tasks ?? 0,
    verifiedClaims: raw.accepted ?? 0,
    pendingClaims: raw.proposed ?? 0,
    disputedClaims: raw.rejected ?? 0,
    totalExperiments: raw.completed ?? 0,
    activeExperiments: raw.in_progress ?? 0,
    hIndex: 0,
    referencesReceived: 0,
  };
}

function mapResearchItem(raw: any): ResearchItem {
  const statusMap: Record<string, ResearchItem["status"]> = {
    accepted: "verified",
    completed: "in_progress",
    voting: "under_debate",
    critique_period: "under_debate",
    proposed: "pending",
    rejected: "retracted",
  };
  return {
    id: raw.id,
    title: raw.title,
    status: statusMap[raw.status] ?? "pending",
    domain: raw.domain,
    agentId: raw.proposed_by,
    score: raw.verification_score ?? 0,
    referenceCount: raw.vote_count ?? 0,
    createdAt: raw.completed_at ?? raw.resolved_at ?? "",
  };
}

function mapRoundtableState(raw: any): RoundtableState {
  const votes = raw.task?.votes ?? [];
  const tally = { approve: 0, reject: 0, abstain: 0 };
  for (const v of votes) {
    if (v.vote in tally) tally[v.vote as keyof typeof tally]++;
  }
  const entries = (raw.discussions || []).map((d: any) => ({
    id: d.id,
    researchItemId: raw.task?.id ?? "",
    agentId: "",
    displayName: d.author_name,
    archetype: "generalist" as const,
    entryType: "argument" as const,
    content: d.body,
    timestamp: d.created_at,
  }));
  // Also include votes as entries
  for (const v of votes) {
    entries.push({
      id: v.id,
      researchItemId: raw.task?.id ?? "",
      agentId: v.agent_id,
      displayName: "",
      archetype: "generalist" as const,
      entryType: "vote" as const,
      content: v.reasoning ?? "",
      vote: v.vote,
      timestamp: v.created_at,
    });
  }
  return {
    researchItemId: raw.task?.id ?? "",
    entries,
    voteTally: tally,
    resolved: ["accepted", "rejected"].includes(raw.task?.status ?? ""),
  };
}

/* eslint-enable @typescript-eslint/no-explicit-any */

// ===========================================
// API FUNCTIONS
// ===========================================

export async function getWorkspaceState(slug: string): Promise<WorkspaceState> {
  if (isMockMode()) return mockGetWorkspaceState(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/workspace/state`);
  if (!res.ok) throw new Error(`Failed to fetch workspace state: ${res.status}`);
  return mapWorkspaceState(await res.json());
}

export function createWorkspaceSSE(slug: string): EventSource {
  return new EventSource(`${API_BASE_URL}/labs/${slug}/workspace/stream`);
}

export async function getLabs(): Promise<LabSummary[]> {
  if (isMockMode()) return mockGetLabs();
  const res = await fetch(`${API_BASE_URL}/labs`);
  if (!res.ok) throw new Error(`Failed to fetch labs: ${res.status}`);
  const data = await res.json();
  // Backend returns PaginatedResponse with items array
  const items = data.items ?? data;
  return (Array.isArray(items) ? items : []).map(mapLabSummary);
}

export async function getLabDetail(slug: string): Promise<LabDetail> {
  if (isMockMode()) return mockGetLabDetail(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}`);
  if (!res.ok) throw new Error(`Failed to fetch lab detail: ${res.status}`);
  return mapLabDetail(await res.json());
}

export async function getLabMembers(slug: string): Promise<LabMember[]> {
  if (isMockMode()) return mockGetLabMembers(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/members`);
  if (!res.ok) throw new Error(`Failed to fetch lab members: ${res.status}`);
  const data = await res.json();
  return (Array.isArray(data) ? data : []).map(mapLabMember);
}

export async function getLabStats(slug: string): Promise<LabStats> {
  if (isMockMode()) return mockGetLabStats(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/stats`);
  if (!res.ok) throw new Error(`Failed to fetch lab stats: ${res.status}`);
  return mapLabStats(await res.json());
}

export async function getLabResearch(slug: string): Promise<ResearchItem[]> {
  if (isMockMode()) return mockGetLabResearch(slug);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/research`);
  if (!res.ok) throw new Error(`Failed to fetch lab research: ${res.status}`);
  const data = await res.json();
  return (Array.isArray(data) ? data : []).map(mapResearchItem);
}

export async function getRoundtable(slug: string, researchItemId: string): Promise<RoundtableState> {
  if (isMockMode()) return mockGetRoundtable(slug, researchItemId);
  const res = await fetch(`${API_BASE_URL}/labs/${slug}/roundtable/${researchItemId}`);
  if (!res.ok) throw new Error(`Failed to fetch roundtable: ${res.status}`);
  return mapRoundtableState(await res.json());
}
