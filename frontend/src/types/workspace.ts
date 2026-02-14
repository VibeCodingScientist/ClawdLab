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
  vRep: number;
  cRep: number;
  labReputation: number;
  globalLevel: number;
  tier: AgentTier;
  prestigeCount: number;
  researchState: AgentResearchState;
  currentTaskId?: string | null;
}

export type LabStateStatus = 'established' | 'under_investigation' | 'contested' | 'proposed' | 'next';

export interface EvidenceEntry {
  type: 'hypothesis' | 'literature' | 'experiment' | 'result' | 'challenge'
    | 'verification' | 'replication' | 'decision' | 'roundtable';
  description: string;
  agent: string;
  dayLabel?: string;
  outcome?: 'confirmed' | 'below_target' | 'inconclusive' | 'rejected' | null;
}

export interface SignatureEntry {
  action: string;
  agent_id: string;
  signature_hash: string;
  timestamp: string;
}

export interface LabStateItem {
  id: string;
  title: string;
  status: LabStateStatus;
  verificationScore: number | null;
  referenceCount: number;
  domain: string;
  proposedBy: string;
  currentSummary?: string;
  signatureChain?: SignatureEntry[];
  evidence: EvidenceEntry[];
}

export interface LabSummary {
  slug: string;
  name: string;
  description: string | null;
  domains: string[];
  tags: string[];
  parentLabId: string | null;
  parentLabSlug: string | null;
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
  vRep: number;
  cRep: number;
  reputation: number;
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
  referencesReceived: number;
}

export interface ResearchItem {
  id: string;
  title: string;
  status: 'verified' | 'in_progress' | 'under_debate' | 'pending' | 'retracted';
  domain: string;
  agentId: string;
  score: number;
  referenceCount: number;
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
