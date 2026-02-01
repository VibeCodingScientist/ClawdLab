/**
 * GameBridge -- EventEmitter singleton bridging React state changes and Phaser scene commands.
 * Depends on: eventemitter3, WorkspaceAgentExtended, WorkspaceZone
 */
import EventEmitter from 'eventemitter3'
import type { WorkspaceAgentExtended, WorkspaceZone, AgentTier, AgentResearchState } from '@/types/workspace'

export interface BridgeEvents {
  // Phaser → React
  agent_clicked: (agentId: string) => void
  agent_hovered: (agentId: string, screenX: number, screenY: number) => void
  agent_unhovered: () => void
  zone_clicked: (zoneId: string) => void
  scene_ready: () => void

  // React → Phaser
  add_agent: (agent: WorkspaceAgentExtended) => void
  move_agent: (agentId: string, zone: WorkspaceZone, x: number, y: number) => void
  remove_agent: (agentId: string) => void
  show_bubble: (agentId: string, text: string, duration: number) => void
  update_agent_status: (agentId: string, status: string) => void
  set_speed: (multiplier: number) => void
  highlight_zone: (zoneId: string, active: boolean) => void

  // React → Phaser (progression)
  update_agent_level: (agentId: string, level: number, tier: AgentTier, prestigeCount: number) => void
  update_agent_research_state: (agentId: string, researchState: AgentResearchState) => void
  agent_level_up: (agentId: string, newLevel: number, color: number) => void
}

class GameBridgeImpl extends EventEmitter<BridgeEvents> {
  private static instance: GameBridgeImpl | null = null

  static getInstance(): GameBridgeImpl {
    if (!GameBridgeImpl.instance) {
      GameBridgeImpl.instance = new GameBridgeImpl()
    }
    return GameBridgeImpl.instance
  }

  static destroy(): void {
    if (GameBridgeImpl.instance) {
      GameBridgeImpl.instance.removeAllListeners()
      GameBridgeImpl.instance = null
    }
  }
}

export const GameBridge = GameBridgeImpl
export type GameBridgeType = GameBridgeImpl
