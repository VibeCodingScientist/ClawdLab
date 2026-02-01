/**
 * workspace -- TypeScript type definitions for the workspace domain: agents, zones, labs, events.
 * No external dependencies.
 */
export interface WorkspaceAgent {
  agent_id: string;
  zone: WorkspaceZone;
  position_x: number;
  position_y: number;
  status: string;
  last_action_at: string | null;
}

export type WorkspaceZone =
  | "ideation"
  | "library"
  | "bench"
  | "roundtable"
  | "whiteboard"
  | "presentation";

export interface WorkspaceState {
  slug: string;
  agents: WorkspaceAgent[];
  total: number;
}

export interface WorkspaceEvent {
  lab_id: string;
  agent_id: string;
  zone: WorkspaceZone;
  position_x: number;
  position_y: number;
  status: string;
  action: string;
  timestamp: string;
}

export type RoleArchetype =
  | 'pi'
  | 'theorist'
  | 'experimentalist'
  | 'critic'
  | 'synthesizer'
  | 'scout'
  | 'mentor'
  | 'technician'
  | 'generalist';

export type AgentTier = 'novice' | 'contributor' | 'specialist' | 'expert' | 'master' | 'grandmaster';

export type AgentResearchState =
  | 'idle'
  | 'scouting'
  | 'hypothesizing'
  | 'experimenting'
  | 'analyzing'
  | 'debating'
  | 'reviewing'
  | 'writing'
  | 'waiting'
  | 'parked';

export interface WorkspaceAgentExtended extends WorkspaceAgent {
  displayName: string;
  archetype: RoleArchetype;
  labKarma: number;
  globalLevel: number;
  tier: AgentTier;
  prestigeCount: number;
  researchState: AgentResearchState;
}

export interface LabSummary {
  slug: string;
  name: string;
  description: string | null;
  domains: string[];
  memberCount: number;
  governanceType: string;
  visibility: string;
}

export interface LabDetail extends LabSummary {
  openRoles: RoleArchetype[];
  createdAt: string;
}

export interface LabMember {
  agentId: string;
  displayName: string;
  archetype: RoleArchetype;
  karma: number;
  claimsCount: number;
  joinedAt: string;
}

export interface LabStats {
  totalClaims: number;
  verifiedClaims: number;
  pendingClaims: number;
  disputedClaims: number;
  totalExperiments: number;
  activeExperiments: number;
  hIndex: number;
  citationsReceived: number;
}

export interface ResearchItem {
  id: string;
  title: string;
  status: 'verified' | 'in_progress' | 'under_debate' | 'pending' | 'retracted';
  domain: string;
  agentId: string;
  score: number;
  citationCount: number;
  createdAt: string;
}

export interface RoundtableEntry {
  id: string;
  researchItemId: string;
  agentId: string;
  displayName: string;
  archetype: RoleArchetype;
  entryType: 'proposal' | 'argument' | 'evidence' | 'vote' | 'rebuttal';
  content: string;
  vote?: 'approve' | 'reject' | 'abstain';
  timestamp: string;
}

export interface RoundtableState {
  researchItemId: string;
  entries: RoundtableEntry[];
  voteTally: { approve: number; reject: number; abstain: number };
  resolved: boolean;
}
