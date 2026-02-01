/**
 * EventProcessor -- Translates GameBridge events into AgentManager commands for the Phaser scene.
 * Depends on: GameBridge, AgentManager, WorkspaceEvent
 */
import { GameBridge } from '../GameBridge'
import type { AgentManager } from './AgentManager'
import type { WorkspaceEvent, WorkspaceAgentExtended, WorkspaceZone } from '@/types/workspace'

export class EventProcessor {
  private bridge = GameBridge.getInstance()
  private agentManager: AgentManager
  private agentLookup: Map<string, WorkspaceAgentExtended> = new Map()

  // Store handler references for proper cleanup
  private handleAddAgent: (agent: WorkspaceAgentExtended) => void
  private handleMoveAgent: (agentId: string, zone: WorkspaceZone, x: number, y: number) => void
  private handleRemoveAgent: (agentId: string) => void
  private handleShowBubble: (agentId: string, text: string, duration: number) => void
  private handleUpdateStatus: (agentId: string, status: string) => void

  constructor(agentManager: AgentManager) {
    this.agentManager = agentManager

    this.handleAddAgent = (agent) => {
      this.agentLookup.set(agent.agent_id, agent)
      this.agentManager.addAgent(agent)
    }

    this.handleMoveAgent = (agentId, zone, x, y) => {
      if (!this.agentManager.getAgent(agentId)) {
        const lookup = this.agentLookup.get(agentId)
        if (lookup) {
          this.agentManager.addAgent(lookup)
        }
      }
      this.agentManager.moveAgent(agentId, zone, x, y)
        .catch(err => console.warn('Agent move failed:', err))
    }

    this.handleRemoveAgent = (agentId) => {
      this.agentManager.removeAgent(agentId)
      this.agentLookup.delete(agentId)
    }

    this.handleShowBubble = (agentId, text, duration) => {
      this.agentManager.showBubble(agentId, text, duration)
    }

    this.handleUpdateStatus = (agentId, status) => {
      this.agentManager.updateStatus(agentId, status)
    }

    this.bridge.on('add_agent', this.handleAddAgent)
    this.bridge.on('move_agent', this.handleMoveAgent)
    this.bridge.on('remove_agent', this.handleRemoveAgent)
    this.bridge.on('show_bubble', this.handleShowBubble)
    this.bridge.on('update_agent_status', this.handleUpdateStatus)
  }

  processWorkspaceEvent(event: WorkspaceEvent): void {
    const existing = this.agentManager.getAgent(event.agent_id)

    if (!existing) {
      const lookup = this.agentLookup.get(event.agent_id)
      if (lookup) {
        const updated = { ...lookup, zone: event.zone, status: event.status }
        this.agentManager.addAgent(updated)
      }
      return
    }

    this.agentManager.moveAgent(
      event.agent_id,
      event.zone,
      event.position_x,
      event.position_y,
    ).catch(err => console.warn('Agent move failed:', err))

    this.agentManager.updateStatus(event.agent_id, event.status)
  }

  setAgentLookup(agents: WorkspaceAgentExtended[]): void {
    this.agentLookup.clear()
    for (const agent of agents) {
      this.agentLookup.set(agent.agent_id, agent)
    }
  }

  destroy(): void {
    this.bridge.off('add_agent', this.handleAddAgent)
    this.bridge.off('move_agent', this.handleMoveAgent)
    this.bridge.off('remove_agent', this.handleRemoveAgent)
    this.bridge.off('show_bubble', this.handleShowBubble)
    this.bridge.off('update_agent_status', this.handleUpdateStatus)
  }
}
