import type { WorkspaceAgentExtended, RoleArchetype } from '@/types/workspace'

export interface AgentSpriteConfig {
  agentId: string
  displayName: string
  archetype: RoleArchetype
  x: number
  y: number
}

export interface AgentHoverPayload {
  agentId: string
  screenX: number
  screenY: number
}

export interface ZoneClickPayload {
  zoneId: string
}

export type { WorkspaceAgentExtended, RoleArchetype }
